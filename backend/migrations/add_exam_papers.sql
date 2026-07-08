-- ============================================================
-- 试卷生成器 (功能2) — 数据库迁移
-- ============================================================

CREATE TABLE IF NOT EXISTS `exam_papers` (
    `id`                 CHAR(36)     NOT NULL COMMENT '试卷ID',
    `user_id`            CHAR(36)     NOT NULL COMMENT '创建教师ID',
    `title`              VARCHAR(200) NOT NULL COMMENT '试卷标题',
    `subject`            VARCHAR(50)  NOT NULL COMMENT '学科',
    `grade`              VARCHAR(50)  NOT NULL COMMENT '年级',
    `exam_type`          VARCHAR(30)  NOT NULL COMMENT '考试类型: unit_test/midterm/final',
    `total_score`        INT          NOT NULL COMMENT '总分',
    `difficulty_ratio`   JSON         NOT NULL COMMENT '难度配比: {"easy":30,"medium":50,"hard":20}',
    `question_structure` JSON         NOT NULL COMMENT '题型分布: [{"type":"选择","count":10,"score_per":3,"subtotal":30}]',
    `content`            JSON         NOT NULL COMMENT '试卷正文JSON: {header,sections[],answer_key,scoring_guide}',
    `answer_sheet`       JSON         NULL     COMMENT '答题卡JSON（服务端自动生成）',
    `export_url`         VARCHAR(500) NULL     COMMENT '导出URL',
    `export_format`      VARCHAR(20)  NULL     COMMENT '导出格式',
    `status`             VARCHAR(20)  NOT NULL DEFAULT 'completed' COMMENT '状态: generating/completed/failed',
    `error_message`      TEXT         NULL     COMMENT '失败错误信息',
    `created_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `ix_ep_user_id` (`user_id`),
    INDEX `ix_ep_subject` (`subject`),
    INDEX `ix_ep_exam_type` (`exam_type`),
    INDEX `ix_ep_created_at` (`created_at`),
    CONSTRAINT `fk_ep_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI试卷生成记录';
