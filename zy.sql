-- ============================================================
-- 智翼（ZhiYi）AI 学习助手平台 — MySQL 完整建表脚本
-- ============================================================
-- 版本:    v3.0
-- 日期:    2026-07-07
-- 数据库:  zhiyi
-- 引擎:    MySQL 8.0+ / InnoDB
-- 字符集:  utf8mb4 / utf8mb4_unicode_ci
-- ============================================================
-- 表清单 (共 21 张):
--   01. users                    用户表（含角色字段）
--   02. learning_profiles        学习档案表
--   03. refresh_tokens           JWT 刷新令牌表
--   04. password_reset_tokens     密码重置令牌表
--   05. chat_sessions            AI 对话会话表
--   06. chat_messages            AI 对话消息表
--   07. summaries                课文总结记录表
--   08. uploaded_files           上传文件表
--   09. exercises                习题表
--   10. exercise_batches         习题批次表
--   11. exercise_attempts        作答记录表
--   12. knowledge_graphs         知识图谱表
--   === 教师端新增 (v3.0) ===
--   13. lesson_plans             智能教案生成记录表
--   14. exam_papers              AI试卷生成记录表
--   15. teaching_resources       教学资源库主表
--   16. resource_favorites       资源收藏表
--   17. resource_download_logs   资源下载日志表
--   18. classes                  班级表
--   19. class_students           班级学生关联表
--   20. assignments              作业表
--   21. assignment_submissions   作业提交表
-- ============================================================


-- ============================================================
-- 建库（如尚未创建，可手动执行下面两行）
-- ============================================================
-- CREATE DATABASE IF NOT EXISTS `zhiyi`
--   DEFAULT CHARACTER SET utf8mb4
--   COLLATE utf8mb4_unicode_ci;
-- USE `zhiyi`;


-- ============================================================
-- 01. users — 用户表 (PBI_01)
-- ============================================================
-- 说明: 平台核心用户账户，支持邮箱 / 手机号登录
--       邮箱和手机号均为可选（至少填一个），唯一索引允许多个 NULL
-- ============================================================
CREATE TABLE IF NOT EXISTS `users` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '用户唯一标识 (UUID v4)',
    `email`             VARCHAR(255)    NULL                                COMMENT '邮箱（唯一，可选）',
    `phone`             VARCHAR(32)     NULL                                COMMENT '手机号（唯一，可选）',
    `hashed_password`   VARCHAR(255)    NOT NULL                            COMMENT 'bcrypt 哈希密码',
    `role`              VARCHAR(20)     NOT NULL DEFAULT 'student'          COMMENT '用户角色: student-学生, teacher-教师, admin-管理员',
    `nickname`          VARCHAR(64)     NOT NULL DEFAULT '同学'              COMMENT '昵称',
    `grade`             VARCHAR(32)     NULL                                COMMENT '年级，如"七年级"',
    `subjects`          JSON            NOT NULL DEFAULT ('[]')             COMMENT '学科偏好列表，如 ["语文","数学"]',
    `textbook_version`  VARCHAR(64)     NULL                                COMMENT '教材版本，如"部编版"',
    `avatar_url`        VARCHAR(512)    NULL                                COMMENT '头像 URL',
    `theme_preferences` JSON            NOT NULL DEFAULT ('{}')             COMMENT '主题偏好设置（护眼模式等）',
    `is_active`         TINYINT(1)      NOT NULL DEFAULT 1                  COMMENT '账户启用状态: 1=启用 0=禁用',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '注册时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `uk_users_email` (`email`),
    UNIQUE INDEX `uk_users_phone` (`phone`),
    INDEX `idx_users_is_active` (`is_active`),
    INDEX `idx_users_role` (`role`),
    INDEX `idx_users_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='用户表';


-- ============================================================
-- 02. learning_profiles — 学习档案表 (PBI_01)
-- ============================================================
-- 说明: 每个用户创建时自动生成一条档案记录，1:1 关系
--       统计指标在作答 / 学习时由后端更新
-- ============================================================
CREATE TABLE IF NOT EXISTS `learning_profiles` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '档案唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID（唯一）',
    `total_study_time`  INT             NOT NULL DEFAULT 0                  COMMENT '累计学习时长（秒）',
    `total_exercises`   INT             NOT NULL DEFAULT 0                  COMMENT '累计做题数',
    `correct_rate`      DOUBLE          NOT NULL DEFAULT 0.0                COMMENT '综合正确率 (0.0 ~ 1.0)',
    `weak_points`       JSON            NOT NULL DEFAULT ('[]')             COMMENT '薄弱知识点列表，如 ["文言文阅读","二次函数"]',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `uk_lp_user_id` (`user_id`),
    CONSTRAINT `fk_lp_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='学习档案表';


-- ============================================================
-- 03. refresh_tokens — JWT 刷新令牌表
-- ============================================================
-- 说明: 存储已签发的 Refresh Token，支持主动失效（登出）和过期清理
--       定期清理过期记录: DELETE FROM refresh_tokens WHERE expires_at < NOW()
-- ============================================================
CREATE TABLE IF NOT EXISTS `refresh_tokens` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '令牌唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `token_hash`        VARCHAR(255)    NOT NULL                            COMMENT '令牌 SHA-256 哈希（防泄露）',
    `expires_at`        DATETIME        NOT NULL                            COMMENT '过期时间',
    `revoked`           TINYINT(1)      NOT NULL DEFAULT 0                  COMMENT '是否已撤销: 1=已撤销',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '签发时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `uk_rt_token_hash` (`token_hash`),
    INDEX `idx_rt_user_id` (`user_id`),
    INDEX `idx_rt_expires_at` (`expires_at`),
    CONSTRAINT `fk_rt_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='JWT 刷新令牌表';


-- ============================================================
-- 04. password_reset_tokens — 密码重置令牌表
-- ============================================================
-- 说明: 用户请求密码重置时生成一次性令牌，有效期 15 分钟
--       用完即删或标记已使用；定期清理过期记录
-- ============================================================
CREATE TABLE IF NOT EXISTS `password_reset_tokens` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '令牌唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `token_hash`        VARCHAR(255)    NOT NULL                            COMMENT '令牌 SHA-256 哈希',
    `expires_at`        DATETIME        NOT NULL                            COMMENT '过期时间（默认签发后 15 分钟）',
    `used`              TINYINT(1)      NOT NULL DEFAULT 0                  COMMENT '是否已使用: 1=已使用',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '签发时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `uk_prt_token_hash` (`token_hash`),
    INDEX `idx_prt_user_id` (`user_id`),
    INDEX `idx_prt_expires_at` (`expires_at`),
    CONSTRAINT `fk_prt_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='密码重置令牌表';


-- ============================================================
-- 05. chat_sessions — AI Agent 对话会话表 (PBI_04)
-- ============================================================
-- 说明: 每次 AI 对话对应一个会话，一个用户可有多个会话
--       常见查询: 按用户 + 最近更新时间倒序排列
-- ============================================================
CREATE TABLE IF NOT EXISTS `chat_sessions` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '会话唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `title`             VARCHAR(255)    NOT NULL DEFAULT '新对话'            COMMENT '会话标题（可由首条消息自动生成）',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近一条消息时间',

    PRIMARY KEY (`id`),
    INDEX `idx_cs_user_updated` (`user_id`, `updated_at` DESC),
    CONSTRAINT `fk_cs_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='AI Agent 对话会话表';


-- ============================================================
-- 06. chat_messages — 对话消息表 (PBI_04, PBI_12)
-- ============================================================
-- 说明: 按 session_id + created_at 排序即可还原对话时间线
--       thought_chain / tool_calls 为 PBI_12 可解释性需求
-- ============================================================
CREATE TABLE IF NOT EXISTS `chat_messages` (
    `id`                INT             NOT NULL AUTO_INCREMENT              COMMENT '消息自增ID（保证时间序）',
    `session_id`        CHAR(36)        NOT NULL                            COMMENT '关联会话ID',
    `role`              VARCHAR(16)     NOT NULL                            COMMENT '角色: user / assistant',
    `content`           TEXT            NOT NULL                            COMMENT '消息文本内容（支持 Markdown）',
    `thought_chain`     JSON            NULL                                COMMENT '思考链步骤 [{step, content, timestamp}]',
    `tool_calls`        JSON            NULL                                COMMENT '工具调用记录 [{tool, args, result}]',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '消息时间',

    PRIMARY KEY (`id`),
    INDEX `idx_cm_session_time` (`session_id`, `created_at`),
    CONSTRAINT `fk_cm_session` FOREIGN KEY (`session_id`)
        REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_cm_role` CHECK (`role` IN ('user', 'assistant'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='对话消息表';


-- ============================================================
-- 07. summaries — 课文总结记录表 (PBI_06)
-- ============================================================
-- 说明: AI 对课文/文本生成摘要及知识点提取
--       source_type: text=直接输入文本, file=上传文件
--       mode: brief=简略模式, detailed=详细模式
-- ============================================================
CREATE TABLE IF NOT EXISTS `summaries` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '总结唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `source_type`       VARCHAR(16)     NOT NULL                            COMMENT '来源类型: text / file',
    `source_content`    TEXT            NOT NULL                            COMMENT '原文内容 或 文件ID引用',
    `summary_text`      TEXT            NOT NULL                            COMMENT 'AI 生成的总结正文',
    `mode`              VARCHAR(16)     NOT NULL DEFAULT 'detailed'          COMMENT '总结模式: brief / detailed',
    `knowledge_points`  JSON            NOT NULL DEFAULT ('[]')             COMMENT '提取的知识点列表 [{name, weight}]',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_sm_user_time` (`user_id`, `created_at` DESC),
    CONSTRAINT `fk_sm_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_sm_source_type` CHECK (`source_type` IN ('text', 'file')),
    CONSTRAINT `chk_sm_mode` CHECK (`mode` IN ('brief', 'detailed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='课文总结记录表';


-- ============================================================
-- 08. uploaded_files — 上传文件表 (PBI_05)
-- ============================================================
-- 说明: 管理用户上传的学习资料文件
--       parse_status 状态机: pending → processing → done / failed
-- ============================================================
CREATE TABLE IF NOT EXISTS `uploaded_files` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '文件唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `filename`          VARCHAR(255)    NOT NULL                            COMMENT '原始文件名（含扩展名）',
    `file_type`         VARCHAR(16)     NOT NULL                            COMMENT '文件类型: pdf / docx / txt / md / csv / json / html / xml / yaml',
    `file_size`         BIGINT          NOT NULL                            COMMENT '文件大小（字节数）',
    `storage_path`      VARCHAR(512)    NOT NULL                            COMMENT '服务器存储路径',
    `parse_status`      VARCHAR(16)     NOT NULL DEFAULT 'pending'          COMMENT '解析状态: pending / processing / done / failed',
    `parsed_content`    TEXT            NULL                                COMMENT '解析出的文本内容（done 时有值）',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '上传时间',

    PRIMARY KEY (`id`),
    INDEX `idx_uf_user_time` (`user_id`, `created_at` DESC),
    INDEX `idx_uf_parse_status` (`parse_status`),
    CONSTRAINT `fk_uf_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_uf_file_type` CHECK (`file_type` IN (
        'pdf', 'docx', 'txt', 'md', 'csv', 'json', 'html', 'xml', 'yaml'
    )),
    CONSTRAINT `chk_uf_parse_status` CHECK (`parse_status` IN (
        'pending', 'processing', 'done', 'failed'
    ))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='上传文件表';


-- ============================================================
-- 09. exercises — 习题表 (PBI_08)
-- ============================================================
-- 说明: AI 生成或用户创建的习题，支持 5 种题型
--       常用筛选: subject + grade + difficulty + question_type
-- ============================================================
CREATE TABLE IF NOT EXISTS `exercises` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '习题唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '创建者用户ID',
    `subject`           VARCHAR(32)     NOT NULL                            COMMENT '学科，如"语文"、"数学"',
    `grade`             VARCHAR(32)     NOT NULL                            COMMENT '年级，如"七年级"、"八年级"',
    `question_type`     VARCHAR(16)     NOT NULL                            COMMENT '题型: choice / fill / short_answer / calculation / analysis',
    `question`          TEXT            NOT NULL                            COMMENT '题目正文',
    `options`           JSON            NULL                                COMMENT '选择题选项 ["A.xxx", "B.xxx", ...]',
    `answer`            TEXT            NOT NULL                            COMMENT '标准答案',
    `analysis`          TEXT            NULL                                COMMENT '解题思路 / 答案解析',
    `difficulty`        VARCHAR(8)      NOT NULL                            COMMENT '难度: easy / medium / hard',
    `knowledge_points`  JSON            NOT NULL DEFAULT ('[]')             COMMENT '关联知识点 ["一元一次方程","..."]',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_ex_user_time` (`user_id`, `created_at` DESC),
    INDEX `idx_ex_filter` (`subject`, `grade`, `difficulty`, `question_type`),
    CONSTRAINT `fk_ex_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_ex_question_type` CHECK (`question_type` IN (
        'choice', 'fill', 'short_answer', 'calculation', 'analysis'
    )),
    CONSTRAINT `chk_ex_difficulty` CHECK (`difficulty` IN ('easy', 'medium', 'hard'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='习题表';


-- ============================================================
-- 10. exercise_batches — 习题批次表 (PBI_09)
-- ============================================================
-- 说明: 一次生成/练习的多道题归为一个批次
--       用于"查看本次练习结果"和"历史练习记录"聚合
-- ============================================================
CREATE TABLE IF NOT EXISTS `exercise_batches` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '批次唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `subject`           VARCHAR(32)     NOT NULL                            COMMENT '学科',
    `grade`             VARCHAR(32)     NOT NULL                            COMMENT '年级',
    `total_count`       INT             NOT NULL                            COMMENT '本次习题总数',
    `correct_count`     INT             NULL                                COMMENT '答对数量（答题完成后填充）',
    `total_score`       DOUBLE          NULL                                COMMENT '总分（答题完成后填充）',
    `status`            VARCHAR(16)     NOT NULL DEFAULT 'pending'          COMMENT '状态: pending=待作答 / doing=作答中 / done=已完成',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `finished_at`       DATETIME        NULL                                COMMENT '完成时间',

    PRIMARY KEY (`id`),
    INDEX `idx_eb_user_time` (`user_id`, `created_at` DESC),
    INDEX `idx_eb_status` (`status`),
    CONSTRAINT `fk_eb_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_eb_status` CHECK (`status` IN ('pending', 'doing', 'done'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='习题批次表';


-- ============================================================
-- 11. exercise_attempts — 作答记录表 (PBI_09, PBI_10)
-- ============================================================
-- 说明: 记录用户对每道题的每次作答
--       通过 batch_id 关联批次，支持"本次练习"聚合
--       graded_by: auto=AI/Auto评分, manual=手动批改
-- ============================================================
CREATE TABLE IF NOT EXISTS `exercise_attempts` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '作答唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '答题者用户ID',
    `exercise_id`       CHAR(36)        NOT NULL                            COMMENT '关联习题ID',
    `batch_id`          CHAR(36)        NULL                                COMMENT '关联批次ID（可选，单题练习时为空）',
    `user_answer`       TEXT            NOT NULL                            COMMENT '用户提交的答案',
    `is_correct`        TINYINT(1)      NULL                                COMMENT '是否答对: 1=对 0=错',
    `score`             DOUBLE          NULL                                COMMENT '得分（0.0 ~ 1.0 或实际分值）',
    `graded_by`         VARCHAR(16)     NOT NULL DEFAULT 'auto'             COMMENT '批改方式: auto / manual',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '提交时间',

    PRIMARY KEY (`id`),
    INDEX `idx_ea_user_time` (`user_id`, `created_at` DESC),
    INDEX `idx_ea_exercise` (`exercise_id`),
    INDEX `idx_ea_batch` (`batch_id`),
    CONSTRAINT `fk_ea_user`     FOREIGN KEY (`user_id`)     REFERENCES `users`     (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ea_exercise` FOREIGN KEY (`exercise_id`) REFERENCES `exercises` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ea_batch`    FOREIGN KEY (`batch_id`)    REFERENCES `exercise_batches` (`id`) ON DELETE SET NULL,
    CONSTRAINT `chk_ea_graded_by` CHECK (`graded_by` IN ('auto', 'manual'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='作答记录表';


-- ============================================================
-- 12. knowledge_graphs — 知识图谱表 (PBI_11)
-- ============================================================
-- 说明: AI 根据学科/章节/文件生成的知识图谱
--       nodes: [{id, label, type, x, y}, ...]
--       edges: [{source, target, relation}, ...]
--       source_type: subject=按学科, chapter=按章节, file=按文件
-- ============================================================
CREATE TABLE IF NOT EXISTS `knowledge_graphs` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '图谱唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `title`             VARCHAR(255)    NOT NULL                            COMMENT '图谱标题（如"初中语文-文言文知识图谱"）',
    `nodes`             JSON            NOT NULL                            COMMENT '图谱节点数组 [{id, label, type, x, y}]',
    `edges`             JSON            NOT NULL                            COMMENT '图谱边数组 [{source, target, relation}]',
    `source_type`       VARCHAR(16)     NOT NULL                            COMMENT '来源类型: subject / chapter / file',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_kg_user_time` (`user_id`, `created_at` DESC),
    CONSTRAINT `fk_kg_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_kg_source_type` CHECK (`source_type` IN ('subject', 'chapter', 'file'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='知识图谱表';


-- ============================================================
-- 13. lesson_plans — 智能教案生成记录表 (教师端)
-- ============================================================
-- 说明: 教师输入学科/年级/章节/课时数，AI 流式生成结构化教案
--       content 为 JSON，包含教学目标/重难点/教学过程/板书设计/反思模板
--       status 状态机: generating → completed / failed
-- ============================================================
CREATE TABLE IF NOT EXISTS `lesson_plans` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '教案ID (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '所属教师ID',
    `title`             VARCHAR(200)    NOT NULL                            COMMENT '教案标题',
    `subject`           VARCHAR(50)     NOT NULL                            COMMENT '学科',
    `grade`             VARCHAR(50)     NOT NULL                            COMMENT '年级',
    `chapter`           VARCHAR(200)    NOT NULL                            COMMENT '章节名称',
    `period_count`      INT             NOT NULL DEFAULT 1                  COMMENT '课时数',
    `content`           JSON            NOT NULL                            COMMENT '教案内容JSON（教学目标/重难点/教学过程/板书设计/反思模板）',
    `export_url`        VARCHAR(500)    NULL                                COMMENT '导出文件URL',
    `export_format`     VARCHAR(20)     NULL                                COMMENT '导出格式: word / pdf',
    `status`            VARCHAR(20)     NOT NULL DEFAULT 'completed'        COMMENT '状态: generating / completed / failed',
    `error_message`     TEXT            NULL                                COMMENT '失败错误信息',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    INDEX `idx_lsp_user_id` (`user_id`),
    INDEX `idx_lsp_subject` (`subject`),
    INDEX `idx_lsp_grade` (`grade`),
    INDEX `idx_lsp_created_at` (`created_at`),
    CONSTRAINT `fk_lsp_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_lsp_status` CHECK (`status` IN ('generating', 'completed', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='智能教案生成记录表';


-- ============================================================
-- 14. exam_papers — AI试卷生成记录表 (教师端)
-- ============================================================
-- 说明: 教师配置题型分布/难度配比，AI 流式生成完整试卷
--       content JSON 含 header/sections/questions/answer_key/scoring_guide
--       answer_sheet 由服务端自动生成，不依赖 AI
-- ============================================================
CREATE TABLE IF NOT EXISTS `exam_papers` (
    `id`                    CHAR(36)        NOT NULL                            COMMENT '试卷ID (UUID v4)',
    `user_id`               CHAR(36)        NOT NULL                            COMMENT '创建教师ID',
    `title`                 VARCHAR(200)    NOT NULL                            COMMENT '试卷标题',
    `subject`               VARCHAR(50)     NOT NULL                            COMMENT '学科',
    `grade`                 VARCHAR(50)     NOT NULL                            COMMENT '年级',
    `exam_type`             VARCHAR(30)     NOT NULL                            COMMENT '考试类型: unit_test / midterm / final',
    `total_score`           INT             NOT NULL                            COMMENT '总分',
    `difficulty_ratio`      JSON            NOT NULL                            COMMENT '难度配比: {"easy":30,"medium":50,"hard":20}',
    `question_structure`    JSON            NOT NULL                            COMMENT '题型分布: [{"type":"选择","count":10,"score_per":3,"subtotal":30}]',
    `content`               JSON            NOT NULL                            COMMENT '试卷正文JSON: {header, sections[{title,instructions,questions[]}], answer_key, scoring_guide}',
    `answer_sheet`          JSON            NULL                                COMMENT '答题卡JSON（服务端自动生成）',
    `export_url`            VARCHAR(500)    NULL                                COMMENT '导出文件URL',
    `export_format`         VARCHAR(20)     NULL                                COMMENT '导出格式: word / pdf / printable',
    `status`                VARCHAR(20)     NOT NULL DEFAULT 'completed'        COMMENT '状态: generating / completed / failed',
    `error_message`         TEXT            NULL                                COMMENT '失败错误信息',
    `created_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                            ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    INDEX `idx_ep_user_id` (`user_id`),
    INDEX `idx_ep_subject` (`subject`),
    INDEX `idx_ep_exam_type` (`exam_type`),
    INDEX `idx_ep_created_at` (`created_at`),
    CONSTRAINT `fk_ep_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_ep_exam_type` CHECK (`exam_type` IN ('unit_test', 'midterm', 'final')),
    CONSTRAINT `chk_ep_status` CHECK (`status` IN ('generating', 'completed', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='AI试卷生成记录表';


-- ============================================================
-- 15. teaching_resources — 教学资源库主表 (教师端)
-- ============================================================
-- 说明: 教师上传/下载/分享课件、试卷、教案等资源
--       公共资源广场 + 个人管理 + 搜索筛选 + 收藏
--       visibility: public=所有人可见, private=仅上传者
--       status: active=正常, deleted=软删除, reviewing=审核中
-- ============================================================
CREATE TABLE IF NOT EXISTS `teaching_resources` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '资源ID (UUID v4)',
    `uploader_id`       CHAR(36)        NOT NULL                            COMMENT '上传者用户ID',
    `title`             VARCHAR(200)    NOT NULL                            COMMENT '资源标题',
    `description`       TEXT            NULL                                COMMENT '资源描述',
    `subject`           VARCHAR(50)     NOT NULL                            COMMENT '学科',
    `grade`             VARCHAR(50)     NOT NULL                            COMMENT '适用年级',
    `resource_type`     VARCHAR(30)     NOT NULL                            COMMENT '资源类型: courseware / exam_paper / lesson_plan / other',
    `file_type`         VARCHAR(20)     NOT NULL                            COMMENT '文件类型: pdf / docx / pptx / xlsx / mp4 / image / txt / zip / mp3',
    `file_name`         VARCHAR(255)    NOT NULL                            COMMENT '原始文件名',
    `file_path`         VARCHAR(500)    NOT NULL                            COMMENT '存储路径',
    `file_size`         BIGINT          NOT NULL                            COMMENT '文件大小（字节）',
    `file_ext`          VARCHAR(10)     NOT NULL                            COMMENT '文件扩展名',
    `download_count`    INT             NOT NULL DEFAULT 0                  COMMENT '下载次数',
    `view_count`        INT             NOT NULL DEFAULT 0                  COMMENT '浏览次数',
    `like_count`        INT             NOT NULL DEFAULT 0                  COMMENT '点赞数',
    `visibility`        VARCHAR(20)     NOT NULL DEFAULT 'public'           COMMENT '可见性: public / private',
    `is_recommended`    TINYINT(1)      NOT NULL DEFAULT 0                  COMMENT '是否推荐: 1=推荐',
    `tags`              JSON            NULL                                COMMENT '标签: ["二次函数","中考复习"]',
    `keywords`          TEXT            NULL                                COMMENT '搜索关键词（FULLTEXT索引）',
    `status`            VARCHAR(20)     NOT NULL DEFAULT 'active'           COMMENT '状态: active / deleted / reviewing',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '上传时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    INDEX `idx_tr_uploader` (`uploader_id`),
    INDEX `idx_tr_subject` (`subject`),
    INDEX `idx_tr_grade` (`grade`),
    INDEX `idx_tr_type` (`resource_type`),
    INDEX `idx_tr_status` (`status`),
    INDEX `idx_tr_created` (`created_at`),
    FULLTEXT INDEX `ft_tr_search` (`title`, `description`, `keywords`),
    CONSTRAINT `fk_tr_uploader` FOREIGN KEY (`uploader_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_tr_resource_type` CHECK (`resource_type` IN ('courseware', 'exam_paper', 'lesson_plan', 'other')),
    CONSTRAINT `chk_tr_file_type` CHECK (`file_type` IN ('pdf', 'docx', 'pptx', 'xlsx', 'mp4', 'image', 'txt', 'zip', 'mp3')),
    CONSTRAINT `chk_tr_visibility` CHECK (`visibility` IN ('public', 'private')),
    CONSTRAINT `chk_tr_status` CHECK (`status` IN ('active', 'deleted', 'reviewing'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='教学资源库主表';


-- ============================================================
-- 16. resource_favorites — 资源收藏表 (教师端)
-- ============================================================
-- 说明: 用户收藏教学资源，user_id + resource_id 联合唯一
-- ============================================================
CREATE TABLE IF NOT EXISTS `resource_favorites` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '收藏记录ID (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '收藏者用户ID',
    `resource_id`       CHAR(36)        NOT NULL                            COMMENT '被收藏资源ID',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '收藏时间',

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_rf_user_res` (`user_id`, `resource_id`),
    CONSTRAINT `fk_rf_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_rf_resource` FOREIGN KEY (`resource_id`)
        REFERENCES `teaching_resources` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='资源收藏表';


-- ============================================================
-- 17. resource_download_logs — 资源下载日志表 (教师端)
-- ============================================================
-- 说明: 记录每次下载行为，用于统计分析和审计
-- ============================================================
CREATE TABLE IF NOT EXISTS `resource_download_logs` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '日志ID (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '下载者用户ID',
    `resource_id`       CHAR(36)        NOT NULL                            COMMENT '被下载资源ID',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '下载时间',

    PRIMARY KEY (`id`),
    INDEX `idx_rdl_user` (`user_id`),
    INDEX `idx_rdl_resource` (`resource_id`),
    INDEX `idx_rdl_created` (`created_at`),
    CONSTRAINT `fk_rdl_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_rdl_resource` FOREIGN KEY (`resource_id`)
        REFERENCES `teaching_resources` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='资源下载日志表';


-- ============================================================
-- 18. classes — 班级表 (教师端 / 师生联动)
-- ============================================================
-- 说明: 教师创建班级并生成邀请码，学生通过邀请码加入
--       invite_code 8位唯一码（排除 0/O/1/I/L 易混淆字符）
--       status: active=活跃, archived=已归档
-- ============================================================
CREATE TABLE IF NOT EXISTS `classes` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '班级ID (UUID v4)',
    `teacher_id`        CHAR(36)        NOT NULL                            COMMENT '班主任/创建教师ID',
    `name`              VARCHAR(100)    NOT NULL                            COMMENT '班级名称（如"高一(3)班数学"）',
    `grade`             VARCHAR(50)     NOT NULL                            COMMENT '年级',
    `subject`           VARCHAR(50)     NOT NULL                            COMMENT '学科',
    `description`       VARCHAR(500)    NULL                                COMMENT '班级描述',
    `invite_code`       CHAR(8)         NOT NULL                            COMMENT '邀请码（8位字母数字，排除易混淆字符）',
    `student_count`     INT             NOT NULL DEFAULT 0                  COMMENT '学生人数（冗余字段，通过触发器或服务层维护）',
    `status`            VARCHAR(20)     NOT NULL DEFAULT 'active'           COMMENT '状态: active / archived',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_class_invite` (`invite_code`),
    INDEX `idx_cls_teacher` (`teacher_id`),
    INDEX `idx_cls_status` (`status`),
    CONSTRAINT `fk_cls_teacher` FOREIGN KEY (`teacher_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_cls_status` CHECK (`status` IN ('active', 'archived'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='班级表';


-- ============================================================
-- 19. class_students — 班级学生关联表 (教师端 / 师生联动)
-- ============================================================
-- 说明: 记录学生加入班级的关联关系
--       class_id + student_id 联合唯一，一个学生可加入多个班级
-- ============================================================
CREATE TABLE IF NOT EXISTS `class_students` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '关联记录ID (UUID v4)',
    `class_id`          CHAR(36)        NOT NULL                            COMMENT '班级ID',
    `student_id`        CHAR(36)        NOT NULL                            COMMENT '学生用户ID',
    `joined_at`         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '加入时间',

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_cs_class_stu` (`class_id`, `student_id`),
    INDEX `idx_cs_student` (`student_id`),
    CONSTRAINT `fk_cs_class` FOREIGN KEY (`class_id`)
        REFERENCES `classes` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cs_student` FOREIGN KEY (`student_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='班级学生关联表';


-- ============================================================
-- 20. assignments — 作业表 (教师端 / 师生联动)
-- ============================================================
-- 说明: 教师在班级中布置作业，content 为 JSON 格式（支持客观题+主观题混合）
--       status: active=进行中, closed=已截止, archived=已归档
-- ============================================================
CREATE TABLE IF NOT EXISTS `assignments` (
    `id`                        CHAR(36)        NOT NULL                            COMMENT '作业ID (UUID v4)',
    `class_id`                  CHAR(36)        NOT NULL                            COMMENT '所属班级ID',
    `teacher_id`                CHAR(36)        NOT NULL                            COMMENT '布置教师ID',
    `title`                     VARCHAR(200)    NOT NULL                            COMMENT '作业标题',
    `description`               TEXT            NULL                                COMMENT '作业说明/要求',
    `subject`                   VARCHAR(50)     NOT NULL                            COMMENT '学科',
    `content`                   JSON            NOT NULL                            COMMENT '作业内容JSON（题型/题目/答案/分值）',
    `total_score`               INT             NULL                                COMMENT '总分（可选）',
    `due_date`                  DATETIME        NOT NULL                            COMMENT '截止提交时间',
    `allow_late_submission`     TINYINT(1)      NOT NULL DEFAULT 0                  COMMENT '是否允许迟交: 1=允许',
    `submission_count`          INT             NOT NULL DEFAULT 0                  COMMENT '已提交人数（冗余）',
    `graded_count`              INT             NOT NULL DEFAULT 0                  COMMENT '已批改人数（冗余）',
    `status`                    VARCHAR(20)     NOT NULL DEFAULT 'active'           COMMENT '状态: active / closed / archived',
    `created_at`                DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '布置时间',
    `updated_at`                DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    INDEX `idx_asgn_class` (`class_id`),
    INDEX `idx_asgn_teacher` (`teacher_id`),
    INDEX `idx_asgn_due` (`due_date`),
    INDEX `idx_asgn_status` (`status`),
    CONSTRAINT `fk_asgn_class` FOREIGN KEY (`class_id`)
        REFERENCES `classes` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_asgn_teacher` FOREIGN KEY (`teacher_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `chk_asgn_status` CHECK (`status` IN ('active', 'closed', 'archived'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='作业表';


-- ============================================================
-- 21. assignment_submissions — 作业提交表 (教师端 / 师生联动)
-- ============================================================
-- 说明: 学生提交作业，AI 辅助批改 + 教师终审
--       status: submitted=已提交, grading=批改中, graded=已批改, returned=已退回
--       assignment_id + student_id 联合唯一（每份作业每人仅可提交一次）
-- ============================================================
CREATE TABLE IF NOT EXISTS `assignment_submissions` (
    `id`                    CHAR(36)        NOT NULL                            COMMENT '提交记录ID (UUID v4)',
    `assignment_id`         CHAR(36)        NOT NULL                            COMMENT '作业ID',
    `student_id`            CHAR(36)        NOT NULL                            COMMENT '提交学生ID',
    `content`               JSON            NOT NULL                            COMMENT '作答内容JSON: {answers: [{question_number, answer}]}',
    `attachments`           JSON            NULL                                COMMENT '附件列表: [{"name":"...","url":"..."}]',
    `score`                 INT             NULL                                COMMENT '得分',
    `ai_feedback`           JSON            NULL                                COMMENT 'AI批改反馈: {overall_comment, question_feedback[], suggested_score}',
    `teacher_feedback`      TEXT            NULL                                COMMENT '教师评语（覆盖/补充AI反馈）',
    `teacher_id`            CHAR(36)        NULL                                COMMENT '批改教师ID',
    `status`                VARCHAR(20)     NOT NULL DEFAULT 'submitted'        COMMENT '状态: submitted / grading / graded / returned',
    `submitted_at`          DATETIME        NULL                                COMMENT '提交时间',
    `graded_at`             DATETIME        NULL                                COMMENT '批改时间',

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_sub_asgn_stu` (`assignment_id`, `student_id`),
    INDEX `idx_sub_student` (`student_id`),
    INDEX `idx_sub_teacher` (`teacher_id`),
    INDEX `idx_sub_status` (`status`),
    CONSTRAINT `fk_sub_asgn` FOREIGN KEY (`assignment_id`)
        REFERENCES `assignments` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_sub_student` FOREIGN KEY (`student_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_sub_teacher` FOREIGN KEY (`teacher_id`)
        REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `chk_sub_status` CHECK (`status` IN ('submitted', 'grading', 'graded', 'returned'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='作业提交表';


-- ============================================================
-- 种子数据 — 开发/测试用
-- ============================================================
-- 密码均为: Test123456 (bcrypt 哈希)
-- 注意: 以下 INSERT 使用 IGNORE 避免重复执行时报错
-- ============================================================

-- 测试用户（密码: Test123456）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `nickname`, `grade`, `subjects`, `textbook_version`)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'demo@zhiyi.com',
    NULL,
    '$2b$12$LJ3m4ys3Lk0TSwHCpNqrNOXUWFxBfDazNGeWG3Vk7yGkvmOS0hZFe',
    '小智',
    '七年级',
    '["语文", "数学", "英语"]',
    '部编版'
);

-- 测试用户的学习档案
INSERT IGNORE INTO `learning_profiles` (`id`, `user_id`, `total_study_time`, `total_exercises`, `correct_rate`, `weak_points`)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    3600,
    45,
    0.78,
    '["文言文阅读", "一元一次方程", "英语完形填空"]'
);


-- ============================================================
-- 测试种子数据（开发/测试用）
-- 密码均为: Test123456!
-- ============================================================

-- 测试用户 1：初中生小明
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `nickname`, `grade`, `subjects`, `textbook_version`, `avatar_url`, `is_active`)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'xiaoming@zhiyi.com',
    '13800000001',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    '小明',
    '七年级',
    '["语文", "数学", "英语"]',
    '部编版',
    NULL,
    1
);

INSERT IGNORE INTO `learning_profiles` (`id`, `user_id`, `total_study_time`, `total_exercises`, `correct_rate`, `weak_points`)
VALUES (
    'b0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    36000,
    128,
    0.85,
    '["文言文阅读", "二次函数", "英语完形填空"]'
);

-- 测试用户 2：高中生小红
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `nickname`, `grade`, `subjects`, `textbook_version`, `avatar_url`, `is_active`)
VALUES (
    'a0000000-0000-0000-0000-000000000002',
    'xiaohong@zhiyi.com',
    '13800000002',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    '小红',
    '高一',
    '["语文", "英语", "物理", "化学"]',
    '人教版',
    NULL,
    1
);

INSERT IGNORE INTO `learning_profiles` (`id`, `user_id`, `total_study_time`, `total_exercises`, `correct_rate`, `weak_points`)
VALUES (
    'b0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000002',
    72000,
    256,
    0.78,
    '["文言文翻译", "力学综合", "有机化学"]'
);

-- 测试用户 3：已禁用的账号（测试登录拒绝）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `nickname`, `grade`, `subjects`, `textbook_version`, `avatar_url`, `is_active`)
VALUES (
    'a0000000-0000-0000-0000-000000000003',
    'disabled@zhiyi.com',
    NULL,
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    '已禁用',
    '九年级',
    '["数学"]',
    NULL,
    NULL,
    0
);

-- ============================================================
-- 存量数据库升级参考（如需从旧版升级，请手动执行以下语句）
-- 新库无需执行 — CREATE TABLE 已包含最新结构
-- ============================================================
-- ALTER TABLE `users` ADD COLUMN `theme_preferences` JSON NOT NULL DEFAULT ('{}') COMMENT '主题偏好' AFTER `avatar_url`;
-- ALTER TABLE `users` ADD COLUMN `role` VARCHAR(20) NOT NULL DEFAULT 'student' COMMENT '角色' AFTER `hashed_password`;
-- CREATE INDEX `idx_users_role` ON `users` (`role`);


-- ============================================================
-- 教师端测试种子数据
-- 密码均为: Test123456!
-- ============================================================

-- 测试教师用户（角色: teacher）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `textbook_version`, `avatar_url`, `is_active`)
VALUES (
    'a0000000-0000-0000-0000-000000000010',
    'teacher@zhiyi.com',
    '13800000010',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    'teacher',
    '王老师',
    '高一',
    '["数学", "物理"]',
    '人教版',
    NULL,
    1
);

-- 测试教师用户 2（角色: teacher）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `textbook_version`, `avatar_url`, `is_active`)
VALUES (
    'a0000000-0000-0000-0000-000000000011',
    'teacher2@zhiyi.com',
    '13800000011',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    'teacher',
    '李老师',
    '八年级',
    '["语文", "英语"]',
    '部编版',
    NULL,
    1
);


-- ============================================================
-- 验证 — 检查所有表是否创建成功
-- ============================================================
-- SELECT TABLE_NAME, TABLE_COMMENT, TABLE_ROWS
-- FROM   information_schema.TABLES
-- WHERE  TABLE_SCHEMA = 'zhiyi'
-- ORDER BY TABLE_NAME;


-- ============================================================
-- 执行完毕 — 共 21 张表 + 种子数据
-- 对应 PBI: 01, 04, 05, 06, 08, 09, 10, 11, 12 + 教师端五大功能模块
-- ============================================================