-- ============================================================
-- 智翼（ZhiYi）AI 学习助手平台 — MySQL 完整建表脚本
-- ============================================================
-- 版本:    v2.0
-- 日期:    2026-07-03
-- 数据库:  zhiyi
-- 引擎:    MySQL 8.0+ / InnoDB
-- 字符集:  utf8mb4 / utf8mb4_unicode_ci
-- ============================================================
-- 表清单 (共 12 张):
--   01. users                用户表
--   02. learning_profiles    学习档案表
--   03. refresh_tokens       JWT 刷新令牌表
--   04. password_reset_tokens 密码重置令牌表
--   05. chat_sessions        AI 对话会话表
--   06. chat_messages        AI 对话消息表
--   07. summaries            课文总结记录表
--   08. uploaded_files       上传文件表
--   09. exercises            习题表
--   10. exercise_batches     习题批次表
--   11. exercise_attempts    作答记录表
--   12. knowledge_graphs     知识图谱表
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
    `nickname`          VARCHAR(64)     NOT NULL DEFAULT '同学'              COMMENT '昵称',
    `grade`             VARCHAR(32)     NULL                                COMMENT '年级，如"七年级"',
    `subjects`          JSON            NOT NULL DEFAULT ('[]')             COMMENT '学科偏好列表，如 ["语文","数学"]',
    `textbook_version`  VARCHAR(64)     NULL                                COMMENT '教材版本，如"部编版"',
    `avatar_url`        VARCHAR(512)    NULL                                COMMENT '头像 URL',
    `is_active`         TINYINT(1)      NOT NULL DEFAULT 1                  COMMENT '账户启用状态: 1=启用 0=禁用',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '注册时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP         COMMENT '最近更新时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `uk_users_email` (`email`),
    UNIQUE INDEX `uk_users_phone` (`phone`),
    INDEX `idx_users_is_active` (`is_active`),
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
-- 验证 — 检查所有表是否创建成功
-- ============================================================
-- SELECT TABLE_NAME, TABLE_COMMENT, TABLE_ROWS
-- FROM   information_schema.TABLES
-- WHERE  TABLE_SCHEMA = 'zhiyi'
-- ORDER BY TABLE_NAME;


-- ============================================================
-- 执行完毕 — 共 12 张表 + 种子数据
-- 对应 PBI: 01, 04, 05, 06, 08, 09, 10, 11, 12
-- ============================================================
