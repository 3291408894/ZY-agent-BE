-- ============================================================
-- 功能3: 教学资源库 — 数据库变更
-- 执行方式: mysql -u root -p zhiyi < migrations/add_teaching_resources.sql
-- ============================================================

-- 1. users 表新增 role 列（角色系统前置依赖）
ALTER TABLE users
  ADD COLUMN `role` VARCHAR(20) NOT NULL DEFAULT 'student'
  COMMENT '用户角色: student-学生, teacher-教师, admin-管理员'
  AFTER `hashed_password`;

CREATE INDEX `ix_users_role` ON `users` (`role`);

-- 2. 教学资源主表
CREATE TABLE IF NOT EXISTS `teaching_resources` (
  `id`              CHAR(36)     NOT NULL COMMENT '资源ID',
  `uploader_id`     CHAR(36)     NOT NULL COMMENT '上传者ID',
  `title`           VARCHAR(200) NOT NULL COMMENT '资源标题',
  `description`     TEXT         NULL     COMMENT '资源描述',
  `subject`         VARCHAR(50)  NOT NULL COMMENT '学科',
  `grade`           VARCHAR(50)  NOT NULL COMMENT '适用年级',
  `resource_type`   VARCHAR(30)  NOT NULL COMMENT '类型: courseware/exam_paper/lesson_plan/other',
  `file_type`       VARCHAR(20)  NOT NULL COMMENT '文件类型: pdf/docx/pptx/xlsx/mp4/image/txt/zip/mp3',
  `file_name`       VARCHAR(255) NOT NULL COMMENT '原始文件名',
  `file_path`       VARCHAR(500) NOT NULL COMMENT '存储路径',
  `file_size`       BIGINT       NOT NULL COMMENT '文件大小(字节)',
  `file_ext`        VARCHAR(10)  NOT NULL COMMENT '文件扩展名',
  `download_count`  INT          NOT NULL DEFAULT 0 COMMENT '下载次数',
  `view_count`      INT          NOT NULL DEFAULT 0 COMMENT '浏览次数',
  `like_count`      INT          NOT NULL DEFAULT 0 COMMENT '点赞数',
  `visibility`      VARCHAR(20)  NOT NULL DEFAULT 'public' COMMENT '可见性: public/private',
  `is_recommended`  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否推荐',
  `tags`            JSON         NULL     COMMENT '标签: ["二次函数","中考复习"]',
  `keywords`        TEXT         NULL     COMMENT '搜索关键词',
  `status`          VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT '状态: active/deleted/reviewing',
  `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `ix_tr_uploader` (`uploader_id`),
  INDEX `ix_tr_subject` (`subject`),
  INDEX `ix_tr_grade` (`grade`),
  INDEX `ix_tr_type` (`resource_type`),
  INDEX `ix_tr_created` (`created_at`),
  CONSTRAINT `fk_tr_uploader` FOREIGN KEY (`uploader_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB CHARSET=utf8mb4 COMMENT='教学资源库';

-- 3. 收藏表
CREATE TABLE IF NOT EXISTS `resource_favorites` (
  `id`          CHAR(36) NOT NULL,
  `user_id`     CHAR(36) NOT NULL,
  `resource_id` CHAR(36) NOT NULL,
  `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rf_user_res` (`user_id`, `resource_id`),
  CONSTRAINT `fk_rf_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rf_resource` FOREIGN KEY (`resource_id`) REFERENCES `teaching_resources`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB CHARSET=utf8mb4 COMMENT='资源收藏';

-- 4. 下载日志表
CREATE TABLE IF NOT EXISTS `resource_download_logs` (
  `id`          CHAR(36) NOT NULL,
  `user_id`     CHAR(36) NOT NULL,
  `resource_id` CHAR(36) NOT NULL,
  `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `ix_rdl_resource` (`resource_id`),
  CONSTRAINT `fk_rdl_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rdl_resource` FOREIGN KEY (`resource_id`) REFERENCES `teaching_resources`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB CHARSET=utf8mb4 COMMENT='资源下载日志';
