-- 为 assignments 表增加 exam_paper_id 字段，建立试卷→作业关联
-- 使从试卷发布创建的作业可以追溯到源试卷
ALTER TABLE assignments ADD COLUMN exam_paper_id VARCHAR(36) NULL
    COMMENT '关联的试卷ID（从试卷发布创建时填充）';
ALTER TABLE assignments ADD INDEX idx_assignments_exam_paper_id (exam_paper_id);
