-- ============================================================
-- 智翼（ZhiYi）AI 学习助手平台 — MySQL 建表脚本
-- 版本: v1.0 | 2026-07-03
-- 对应文档: 智翼平台开发规范与接口文档.md §4.1
-- 数据库名: zhiyi (请先手动创建)
-- ============================================================

-- 创建数据库（如尚未创建）
-- CREATE DATABASE IF NOT EXISTS zhiyi DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE zhiyi;

-- ============================================================
-- 1. users — 用户表 (PBI_01)
-- ============================================================
CREATE TABLE IF NOT EXISTS `users` (
    `id`                CHAR(36)        NOT NULL COMMENT '用户唯一标识 (UUID v4)',
    `email`             VARCHAR(255)    NULL     COMMENT '邮箱',
    `phone`             VARCHAR(32)     NULL     COMMENT '手机号',
    `hashed_password`   VARCHAR(255)    NOT NULL COMMENT 'bcrypt 哈希密码',
    `nickname`          VARCHAR(64)     NOT NULL DEFAULT '同学'   COMMENT '昵称',
    `grade`             VARCHAR(32)     NULL     COMMENT '年级，如"七年级"',
    `subjects`          JSON            NOT NULL COMMENT '学科偏好列表，如 ["语文","数学"]',
    `textbook_version`  VARCHAR(64)     NULL     COMMENT '教材版本，如"部编版"',
    `avatar_url`        VARCHAR(512)    NULL     COMMENT '头像 URL',
    `is_active`         TINYINT(1)      NOT NULL DEFAULT 1       COMMENT '账户启用状态',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP           COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `idx_users_email` (`email`),
    UNIQUE INDEX `idx_users_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';


-- ============================================================
-- 2. learning_profiles — 学习档案表 (PBI_01)
-- ============================================================
CREATE TABLE IF NOT EXISTS `learning_profiles` (
    `id`                CHAR(36)        NOT NULL COMMENT '档案唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL COMMENT '关联用户ID',
    `total_study_time`  INT             NOT NULL DEFAULT 0       COMMENT '累计学习时长（秒）',
    `total_exercises`   INT             NOT NULL DEFAULT 0       COMMENT '累计做题数',
    `correct_rate`      DOUBLE          NOT NULL DEFAULT 0.0     COMMENT '正确率',
    `weak_points`       JSON            NOT NULL COMMENT '薄弱知识点列表',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (`id`),
    UNIQUE INDEX `idx_lp_user_id` (`user_id`),
    CONSTRAINT `fk_lp_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学习档案表';


-- ============================================================
-- 3. chat_sessions — AI Agent 对话会话表 (PBI_04)
-- ============================================================
CREATE TABLE IF NOT EXISTS `chat_sessions` (
    `id`                CHAR(36)        NOT NULL COMMENT '会话唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL COMMENT '关联用户ID',
    `title`             VARCHAR(255)    NOT NULL DEFAULT '新对话' COMMENT '会话标题',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP           COMMENT '创建时间',
    `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (`id`),
    INDEX `idx_cs_user_id` (`user_id`),
    CONSTRAINT `fk_cs_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话会话表';


-- ============================================================
-- 4. chat_messages — 对话消息表 (PBI_04, PBI_12)
-- ============================================================
CREATE TABLE IF NOT EXISTS `chat_messages` (
    `id`                INT             NOT NULL AUTO_INCREMENT COMMENT '消息自增ID',
    `session_id`        CHAR(36)        NOT NULL COMMENT '关联会话ID',
    `role`              VARCHAR(16)     NOT NULL COMMENT '角色: user / assistant',
    `content`           TEXT            NOT NULL COMMENT '消息文本内容',
    `thought_chain`     JSON            NULL     COMMENT '思考链步骤 (PBI_12)',
    `tool_calls`        JSON            NULL     COMMENT '工具调用记录 (PBI_12)',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_cm_session_id` (`session_id`),
    CONSTRAINT `fk_cm_session` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话消息表';


-- ============================================================
-- 5. summaries — 课文总结记录表 (PBI_06)
-- ============================================================
CREATE TABLE IF NOT EXISTS `summaries` (
    `id`                CHAR(36)        NOT NULL COMMENT '总结唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL COMMENT '关联用户ID',
    `source_type`       VARCHAR(16)     NOT NULL COMMENT '来源类型: text / file',
    `source_content`    TEXT            NOT NULL COMMENT '原文 或 文件ID引用',
    `summary_text`      TEXT            NOT NULL COMMENT 'AI 生成的总结正文',
    `mode`              VARCHAR(16)     NOT NULL DEFAULT 'detailed' COMMENT '总结模式: brief / detailed',
    `knowledge_points`  JSON            NOT NULL COMMENT '提取的知识点列表',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_sm_user_id` (`user_id`),
    CONSTRAINT `fk_sm_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='课文总结记录表';


-- ============================================================
-- 6. uploaded_files — 上传文件表 (PBI_05)
-- ============================================================
CREATE TABLE IF NOT EXISTS `uploaded_files` (
    `id`                CHAR(36)        NOT NULL COMMENT '文件唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL COMMENT '关联用户ID',
    `filename`          VARCHAR(255)    NOT NULL COMMENT '原始文件名',
    `file_type`         VARCHAR(16)     NOT NULL COMMENT '文件类型: pdf / docx / txt / md / csv / json / html / xml / yaml',
    `file_size`         BIGINT          NOT NULL COMMENT '文件大小（字节数）',
    `storage_path`      VARCHAR(512)    NOT NULL COMMENT '存储路径',
    `parse_status`      VARCHAR(16)     NOT NULL DEFAULT 'pending' COMMENT '解析状态: pending / processing / done / failed',
    `parsed_content`    TEXT            NULL     COMMENT '解析出的文本内容',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_uf_user_id` (`user_id`),
    CONSTRAINT `fk_uf_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='上传文件表';


-- ============================================================
-- 7. exercises — 习题表 (PBI_08)
-- ============================================================
CREATE TABLE IF NOT EXISTS `exercises` (
    `id`                CHAR(36)        NOT NULL COMMENT '习题唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL COMMENT '关联用户ID（创建者）',
    `subject`           VARCHAR(32)     NOT NULL COMMENT '学科，如"语文"',
    `grade`             VARCHAR(32)     NOT NULL COMMENT '年级，如"七年级"',
    `question_type`     VARCHAR(32)     NOT NULL COMMENT '题型: choice / fill / short_answer / calculation / analysis',
    `question`          TEXT            NOT NULL COMMENT '题目正文',
    `options`           JSON            NULL     COMMENT '选择题选项列表',
    `answer`            TEXT            NOT NULL COMMENT '标准答案',
    `analysis`          TEXT            NULL     COMMENT '解题思路 / 答案解析',
    `difficulty`        VARCHAR(16)     NOT NULL COMMENT '难度: easy / medium / hard',
    `knowledge_points`  JSON            NOT NULL COMMENT '关联知识点列表',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_ex_user_id` (`user_id`),
    CONSTRAINT `fk_ex_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='习题表';


-- ============================================================
-- 8. exercise_attempts — 作答记录表 (PBI_09, PBI_10)
-- ============================================================
CREATE TABLE IF NOT EXISTS `exercise_attempts` (
    `id`                CHAR(36)        NOT NULL COMMENT '作答唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL COMMENT '关联用户ID（答题者）',
    `exercise_id`       CHAR(36)        NOT NULL COMMENT '关联习题ID',
    `user_answer`       TEXT            NOT NULL COMMENT '用户提交的答案',
    `is_correct`        TINYINT(1)      NULL     COMMENT '是否答对',
    `score`             DOUBLE          NULL     COMMENT '得分',
    `graded_by`         VARCHAR(16)     NOT NULL DEFAULT 'auto' COMMENT '批改方式: auto / manual',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_ea_user_id` (`user_id`),
    INDEX `idx_ea_exercise_id` (`exercise_id`),
    CONSTRAINT `fk_ea_user`     FOREIGN KEY (`user_id`)     REFERENCES `users`     (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ea_exercise` FOREIGN KEY (`exercise_id`) REFERENCES `exercises` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='作答记录表';


-- ============================================================
-- 9. knowledge_graphs — 知识图谱表 (PBI_11)
-- ============================================================
CREATE TABLE IF NOT EXISTS `knowledge_graphs` (
    `id`                CHAR(36)        NOT NULL COMMENT '图谱唯一标识 (UUID v4)',
    `user_id`           CHAR(36)        NOT NULL COMMENT '关联用户ID',
    `title`             VARCHAR(255)    NOT NULL COMMENT '图谱标题',
    `nodes`             JSON            NOT NULL COMMENT '图谱节点 [{id, label, type, x, y}]',
    `edges`             JSON            NOT NULL COMMENT '图谱边 [{source, target, relation}]',
    `source_type`       VARCHAR(16)     NOT NULL COMMENT '来源类型: subject / chapter / file',
    `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    PRIMARY KEY (`id`),
    INDEX `idx_kg_user_id` (`user_id`),
    CONSTRAINT `fk_kg_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识图谱表';

-- ============================================================
-- 执行完毕：共 9 张表
-- ============================================================


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
