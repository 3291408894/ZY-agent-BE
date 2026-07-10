-- ============================================================
-- 智翼（ZhiYi）AI 学习助手平台 — MySQL 完整建表脚本
-- ============================================================
-- 版本:    v3.2
-- 日期:    2026-07-10
-- 数据库:  zhiyi
-- 引擎:    MySQL 8.0+ / InnoDB
-- 字符集:  utf8mb4 / utf8mb4_unicode_ci
-- 来源:    实际数据库 mysqldump 导出
-- ============================================================
-- 表清单 (共 23 张):
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
--   === v3.2 新增 ===
--   22. class_resources          班级资源分享表
--   23. class_exam_papers        班级试卷分享表
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
    `email`             VARCHAR(255)    NULL                                COMMENT '邮箱',
    `phone`             VARCHAR(32)     NULL                                COMMENT '手机号',
    `hashed_password`   VARCHAR(255)    NOT NULL                            COMMENT 'bcrypt 哈希密码',
    `role`              VARCHAR(20)     NOT NULL DEFAULT 'student'          COMMENT '用户角色: student-学生, teacher-教师, admin-管理员',
    `nickname`          VARCHAR(64)     NOT NULL DEFAULT '同学'              COMMENT '昵称',
    `grade`             VARCHAR(32)     NULL                                COMMENT '年级，如"七年级"',
    `subjects`          JSON            NOT NULL                            COMMENT '学科偏好列表，如 ["语文","数学"]',
    `textbook_version`  VARCHAR(64)     NULL                                COMMENT '教材版本，如"部编版"',
    `avatar_url`        VARCHAR(512)    NULL                                COMMENT '头像 URL',
    `school_name`       VARCHAR(128)    NULL                                COMMENT '教师所属学校',
    `bio`               VARCHAR(512)    NULL                                COMMENT '教师简介/个人介绍',
    `theme_preferences` JSON            NOT NULL DEFAULT ('{}')             COMMENT '主题偏好设置（护眼模式等）',
    `is_active`         TINYINT(1)      NOT NULL DEFAULT 1                  COMMENT '账户启用状态: 1=启用 0=禁用',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '更新时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `idx_users_email` (`email`),
    UNIQUE INDEX `idx_users_phone` (`phone`),
    INDEX `idx_users_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户表';


-- ============================================================
-- 02. learning_profiles — 学习档案表 (PBI_01)
-- ============================================================
-- 说明: 每个用户创建时自动生成一条档案记录，1:1 关系
--       统计指标在作答 / 学习时由后端更新
-- ============================================================
CREATE TABLE IF NOT EXISTS `learning_profiles` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '档案唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID',
    `total_study_time`  INT             NOT NULL DEFAULT 0                  COMMENT '累计学习时长（秒）',
    `total_exercises`   INT             NOT NULL DEFAULT 0                  COMMENT '累计做题数',
    `correct_rate`      DOUBLE          NOT NULL DEFAULT 0                  COMMENT '正确率',
    `weak_points`       JSON            NOT NULL                            COMMENT '薄弱知识点列表',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '更新时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `idx_lp_user_id` (`user_id`),
    CONSTRAINT `fk_lp_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
    `title`             VARCHAR(255)    NOT NULL DEFAULT '新对话'            COMMENT '会话标题',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '更新时间',

    PRIMARY KEY (`id`),
    INDEX `idx_cs_user_id` (`user_id`),
    CONSTRAINT `fk_cs_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='对话会话表';


-- ============================================================
-- 06. chat_messages — 对话消息表 (PBI_04, PBI_12)
-- ============================================================
-- 说明: 按 session_id + created_at 排序即可还原对话时间线
--       thought_chain / tool_calls 为 PBI_12 可解释性需求
-- ============================================================
CREATE TABLE IF NOT EXISTS `chat_messages` (
    `id`                INT             NOT NULL AUTO_INCREMENT              COMMENT '消息自增ID',
    `session_id`        CHAR(36)        NOT NULL                            COMMENT '关联会话ID',
    `role`              VARCHAR(16)     NOT NULL                            COMMENT '角色: user / assistant',
    `content`           TEXT            NOT NULL                            COMMENT '消息文本内容',
    `thought_chain`     JSON            NULL                                COMMENT '思考链步骤 (PBI_12)',
    `tool_calls`        JSON            NULL                                COMMENT '工具调用记录 (PBI_12)',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_cm_session_id` (`session_id`),
    CONSTRAINT `fk_cm_session` FOREIGN KEY (`session_id`)
        REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
    `source_content`    TEXT            NOT NULL                            COMMENT '原文 或 文件ID引用',
    `summary_text`      TEXT            NOT NULL                            COMMENT 'AI 生成的总结正文',
    `mode`              VARCHAR(16)     NOT NULL DEFAULT 'detailed'          COMMENT '总结模式: brief / detailed',
    `knowledge_points`  JSON            NOT NULL                            COMMENT '提取的知识点列表',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_sm_user_id` (`user_id`),
    CONSTRAINT `fk_sm_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
    `filename`          VARCHAR(255)    NOT NULL                            COMMENT '原始文件名',
    `file_type`         VARCHAR(16)     NOT NULL                            COMMENT '文件类型: pdf / docx / txt / md / csv / json / html / xml / yaml',
    `file_size`         BIGINT          NOT NULL                            COMMENT '文件大小（字节数）',
    `storage_path`      VARCHAR(512)    NOT NULL                            COMMENT '存储路径',
    `parse_status`      VARCHAR(16)     NOT NULL DEFAULT 'pending'          COMMENT '解析状态: pending / processing / done / failed',
    `parsed_content`    TEXT            NULL                                COMMENT '解析出的文本内容',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_uf_user_id` (`user_id`),
    CONSTRAINT `fk_uf_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='上传文件表';


-- ============================================================
-- 09. exercises — 习题表 (PBI_08)
-- ============================================================
-- 说明: AI 生成或用户创建的习题，支持 5 种题型
--       batch_id 关联习题批次（可为空）
-- ============================================================
CREATE TABLE IF NOT EXISTS `exercises` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '习题唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID（创建者）',
    `subject`           VARCHAR(32)     NOT NULL                            COMMENT '学科，如"语文"',
    `grade`             VARCHAR(32)     NOT NULL                            COMMENT '年级，如"七年级"',
    `question_type`     VARCHAR(32)     NOT NULL                            COMMENT '题型: choice / fill / short_answer / calculation / analysis',
    `question`          TEXT            NOT NULL                            COMMENT '题目正文',
    `options`           JSON            NULL                                COMMENT '选择题选项列表',
    `answer`            TEXT            NOT NULL                            COMMENT '标准答案',
    `analysis`          TEXT            NULL                                COMMENT '解题思路 / 答案解析',
    `difficulty`        VARCHAR(16)     NOT NULL                            COMMENT '难度: easy / medium / hard',
    `knowledge_points`  JSON            NOT NULL                            COMMENT '关联知识点列表',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `batch_id`          VARCHAR(36)     NULL                                COMMENT '关联批次ID',

    PRIMARY KEY (`id`),
    INDEX `idx_ex_user_id` (`user_id`),
    INDEX `idx_exercises_batch_id` (`batch_id`),
    CONSTRAINT `fk_ex_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
--       graded_by: auto=AI/Auto评分, manual=手动批改
-- ============================================================
CREATE TABLE IF NOT EXISTS `exercise_attempts` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '作答唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL                            COMMENT '关联用户ID（答题者）',
    `exercise_id`       CHAR(36)        NOT NULL                            COMMENT '关联习题ID',
    `user_answer`       TEXT            NOT NULL                            COMMENT '用户提交的答案',
    `is_correct`        TINYINT(1)      NULL                                COMMENT '是否答对',
    `score`             DOUBLE          NULL                                COMMENT '得分',
    `graded_by`         VARCHAR(16)     NOT NULL DEFAULT 'auto'             COMMENT '批改方式: auto / manual',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_ea_user_id` (`user_id`),
    INDEX `idx_ea_exercise_id` (`exercise_id`),
    CONSTRAINT `fk_ea_exercise` FOREIGN KEY (`exercise_id`)
        REFERENCES `exercises` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ea_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
    `title`             VARCHAR(255)    NOT NULL                            COMMENT '图谱标题',
    `nodes`             JSON            NOT NULL                            COMMENT '图谱节点 [{id, label, type, x, y}]',
    `edges`             JSON            NOT NULL                            COMMENT '图谱边 [{source, target, relation}]',
    `source_type`       VARCHAR(16)     NOT NULL                            COMMENT '来源类型: subject / chapter / file',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_kg_user_id` (`user_id`),
    CONSTRAINT `fk_kg_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='知识图谱表';


-- ============================================================
-- 13. lesson_plans — 智能教案生成记录表 (教师端)
-- ============================================================
-- 说明: 教师输入学科/年级/章节/课时数，AI 流式生成结构化教案
--       content 为 JSON，包含教学目标/重难点/教学过程/板书设计/反思模板
-- ============================================================
CREATE TABLE IF NOT EXISTS `lesson_plans` (
    `id`                    CHAR(36)        NOT NULL                            COMMENT '主键 UUID',
    `user_id`               CHAR(36)        NOT NULL                            COMMENT '所属用户',
    `title`                 VARCHAR(128)    NOT NULL DEFAULT '未命名教案'        COMMENT '教案标题',
    `subject`               VARCHAR(32)     NOT NULL                            COMMENT '学科',
    `grade`                 VARCHAR(16)     NOT NULL                            COMMENT '年级',
    `textbook_version`      VARCHAR(64)     NOT NULL DEFAULT ''                 COMMENT '教材版本',
    `unit_chapter`          VARCHAR(128)    NOT NULL DEFAULT ''                 COMMENT '单元/章节',
    `class_hours`           INT             NOT NULL DEFAULT 1                  COMMENT '课时数',
    `teaching_objectives`   TEXT            NULL                                COMMENT '教学目标',
    `requirements`          TEXT            NULL                                COMMENT '特殊要求',
    `plan_content`          TEXT            NULL                                COMMENT '教案正文(Markdown)',
    `sections`              JSON            NULL                                COMMENT '结构化分段信息',
    `created_at`            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_lp_user` (`user_id`),
    INDEX `idx_lp_subject` (`subject`),
    INDEX `idx_lp_grade` (`grade`),
    INDEX `idx_lp_created` (`created_at`),
    CONSTRAINT `fk_lesson_plans_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='教案生成记录表';


-- ============================================================
-- 14. exam_papers — AI试卷生成记录表 (教师端)
-- ============================================================
-- 说明: 教师配置题型分布/难度配比，AI 流式生成完整试卷
--       content JSON 含 header/sections/questions/answer_key/scoring_guide
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
    INDEX `fk_rf_resource` (`resource_id`),
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
    `student_count`     INT             NOT NULL DEFAULT 0                  COMMENT '学生人数（冗余字段，通过服务层维护）',
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
--       exam_paper_id 关联试卷（从试卷发布创建时填充）
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
    `exam_paper_id`             VARCHAR(36)     NULL                                COMMENT '关联的试卷ID（从试卷发布创建时填充）',

    PRIMARY KEY (`id`),
    INDEX `idx_asgn_class` (`class_id`),
    INDEX `idx_asgn_teacher` (`teacher_id`),
    INDEX `idx_asgn_due` (`due_date`),
    INDEX `idx_asgn_status` (`status`),
    INDEX `idx_assignments_exam_paper_id` (`exam_paper_id`),
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
-- 22. class_resources — 班级资源分享表 (教师端 / 师生联动)
-- ============================================================
-- 说明: 教师将教学资源分享到班级，学生可在班级中查看和下载
--       class_id + resource_id 联合唯一
-- ============================================================
CREATE TABLE IF NOT EXISTS `class_resources` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '分享记录ID (UUID v4)',
    `class_id`          CHAR(36)        NOT NULL                            COMMENT '班级ID',
    `resource_id`       CHAR(36)        NOT NULL                            COMMENT '教学资源ID',
    `shared_by`         CHAR(36)        NOT NULL                            COMMENT '分享教师ID',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '分享时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `uk_cr_class_resource` (`class_id`, `resource_id`),
    INDEX `idx_cr_class_id` (`class_id`),
    INDEX `idx_cr_resource_id` (`resource_id`),
    INDEX `fk_cr_teacher` (`shared_by`),
    CONSTRAINT `fk_cr_class` FOREIGN KEY (`class_id`)
        REFERENCES `classes` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cr_resource` FOREIGN KEY (`resource_id`)
        REFERENCES `teaching_resources` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cr_teacher` FOREIGN KEY (`shared_by`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='班级资源分享表';


-- ============================================================
-- 23. class_exam_papers — 班级试卷分享表 (教师端 / 师生联动)
-- ============================================================
-- 说明: 教师将AI生成的试卷分享到班级，学生可在班级中查看
--       class_id + exam_paper_id 联合唯一
-- ============================================================
CREATE TABLE IF NOT EXISTS `class_exam_papers` (
    `id`                CHAR(36)        NOT NULL                            COMMENT '分享记录ID (UUID v4)',
    `class_id`          CHAR(36)        NOT NULL                            COMMENT '班级ID',
    `exam_paper_id`     CHAR(36)        NOT NULL                            COMMENT '试卷ID',
    `shared_by`         CHAR(36)        NOT NULL                            COMMENT '分享教师ID',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '分享时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `uq_cep_class_paper` (`class_id`, `exam_paper_id`),
    INDEX `idx_cep_class_id` (`class_id`),
    INDEX `idx_cep_exam_paper_id` (`exam_paper_id`),
    INDEX `fk_cep_teacher` (`shared_by`),
    CONSTRAINT `fk_cep_class` FOREIGN KEY (`class_id`)
        REFERENCES `classes` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cep_exam_paper` FOREIGN KEY (`exam_paper_id`)
        REFERENCES `exam_papers` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_cep_teacher` FOREIGN KEY (`shared_by`)
        REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  ROW_FORMAT=DYNAMIC
  COMMENT='班级试卷分享表';


-- ============================================================
-- 种子数据 — 开发/测试用
-- ============================================================
-- 密码均为: Test123456
-- 注意: 以下 INSERT 使用 IGNORE 避免重复执行时报错
-- ============================================================

-- 测试用户：小智（密码: Test123456）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `textbook_version`)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'demo@zhiyi.com',
    NULL,
    '$2b$12$LJ3m4ys3Lk0TSwHCpNqrNOXUWFxBfDazNGeWG3Vk7yGkvmOS0hZFe',
    'student',
    '小智',
    '七年级',
    '["语文", "数学", "英语"]',
    '部编版'
);

INSERT IGNORE INTO `learning_profiles` (`id`, `user_id`, `total_study_time`, `total_exercises`, `correct_rate`, `weak_points`)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    3600,
    45,
    0.78,
    '["文言文阅读", "一元一次方程", "英语完形填空"]'
);

-- 测试用户：小明（密码: Test123456!）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `textbook_version`)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'xiaoming@zhiyi.com',
    '13800000001',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    'student',
    '小明',
    '七年级',
    '["语文", "数学", "英语"]',
    '部编版'
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

-- 测试用户：小红（密码: Test123456!）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `textbook_version`)
VALUES (
    'a0000000-0000-0000-0000-000000000002',
    'xiaohong@zhiyi.com',
    '13800000002',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    'student',
    '小红',
    '高一',
    '["语文", "英语", "物理", "化学"]',
    '人教版'
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

-- 测试用户：已禁用账号（密码: Test123456!）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `is_active`)
VALUES (
    'a0000000-0000-0000-0000-000000000003',
    'disabled@zhiyi.com',
    NULL,
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    'student',
    '已禁用',
    '九年级',
    '["数学"]',
    0
);

-- 测试教师：王老师（密码: Test123456!）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `textbook_version`)
VALUES (
    'a0000000-0000-0000-0000-000000000010',
    'teacher@zhiyi.com',
    '13800000010',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    'teacher',
    '王老师',
    '高一',
    '["数学", "物理"]',
    '人教版'
);

-- 测试教师：李老师（密码: Test123456!）
INSERT IGNORE INTO `users` (`id`, `email`, `phone`, `hashed_password`, `role`, `nickname`, `grade`, `subjects`, `textbook_version`)
VALUES (
    'a0000000-0000-0000-0000-000000000011',
    'teacher2@zhiyi.com',
    '13800000011',
    '$2b$12$RJkqRd6FuFzEd/FvjEoit.QZJAxc/XfwSnQzeipvvE.1ZiQNCFPtu',
    'teacher',
    '李老师',
    '八年级',
    '["语文", "英语"]',
    '部编版'
);


-- ============================================================
-- 存量数据库升级参考（如需从旧版升级，请执行以下 ALTER 语句）
-- 新库无需执行 — CREATE TABLE 已包含最新结构
-- ============================================================

-- v3.0 → v3.1: users 表新增教师信息字段
-- ALTER TABLE `users`
--     ADD COLUMN IF NOT EXISTS `school_name` VARCHAR(128) NULL COMMENT '教师所属学校' AFTER `avatar_url`,
--     ADD COLUMN IF NOT EXISTS `bio`         VARCHAR(512) NULL COMMENT '教师简介/个人介绍' AFTER `school_name`;

-- v3.1 → v3.2: assignments 表新增 exam_paper_id 字段
-- ALTER TABLE `assignments`
--     ADD COLUMN IF NOT EXISTS `exam_paper_id` VARCHAR(36) NULL COMMENT '关联的试卷ID' AFTER `updated_at`,
--     ADD INDEX IF NOT EXISTS `idx_assignments_exam_paper_id` (`exam_paper_id`);

-- v3.1 → v3.2: exercises 表新增 batch_id 字段
-- ALTER TABLE `exercises`
--     ADD COLUMN IF NOT EXISTS `batch_id` VARCHAR(36) NULL COMMENT '关联批次ID' AFTER `created_at`,
--     ADD INDEX IF NOT EXISTS `idx_exercises_batch_id` (`batch_id`);


-- ============================================================
-- 验证 — 检查所有表是否创建成功
-- ============================================================
-- SELECT TABLE_NAME, TABLE_COMMENT, TABLE_ROWS
-- FROM   information_schema.TABLES
-- WHERE  TABLE_SCHEMA = 'zhiyi'
-- ORDER BY TABLE_NAME;


-- ============================================================
-- 执行完毕 — 共 23 张表 + 种子数据
-- 对应 PBI: 01, 04, 05, 06, 08, 09, 10, 11, 12 + 教师端五大功能模块
-- ============================================================

ALTER TABLE assignments ADD COLUMN IF NOT EXISTS exam_paper_id CHAR(36) NULL COMMENT '关联试卷ID';