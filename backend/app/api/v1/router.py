"""
API v1 路由聚合 — 按文档规范组织所有子路由
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.agent import router as agent_router

# ============================================================
# 功能模块路由
# ============================================================
from app.api.v1.summary import router as summary_router
from app.api.v1.exercises import router as exercises_router
from app.api.v1.files import router as files_router
from app.api.v1.knowledge import router as knowledge_router

# ============================================================
# 教师端路由 (功能模块)
# ============================================================
from app.api.v1.teacher.resources import router as teacher_resources_router
from app.api.v1.teacher.classes import router as teacher_classes_router
from app.api.v1.teacher.assignments import router as teacher_assignments_router

# ============================================================
# 学生端路由 (师生联动模块)
# ============================================================
from app.api.v1.student.classes import router as student_classes_router
from app.api.v1.student.assignments import router as student_assignments_router

api_router = APIRouter(prefix="/api/v1")

# --- 认证模块 (PBI_01) ✅ 已激活 ---
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])

# --- 用户模块 (PBI_01) ✅ 已激活 ---
api_router.include_router(users_router, prefix="/users", tags=["用户"])

# --- AI Agent 模块 (PBI_04, PBI_12) ✅ 已激活 ---
api_router.include_router(agent_router, prefix="/agent", tags=["AI Agent"])

# --- 课文总结模块 (PBI_06) ✅ 已激活 ---
api_router.include_router(summary_router, prefix="/summaries", tags=["课文总结"])

# --- 习题模块 (PBI_08, PBI_09, PBI_10) ✅ 已激活 ---
api_router.include_router(exercises_router, prefix="/exercises", tags=["习题"])

# --- 文件管理模块 (PBI_05) ✅ 已激活 ---
api_router.include_router(files_router, prefix="/files", tags=["文件管理"])

# --- 知识图谱模块 (PBI_11) ✅ 已激活 ---
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识图谱"])

# --- 教师端 — 教学资源库 (功能3) ✅ 已激活 ---
api_router.include_router(teacher_resources_router, prefix="/teacher/resources", tags=["教师-教学资源库"])

# --- 教师端 — 班级管理 (功能4) ✅ 已激活 ---
api_router.include_router(teacher_classes_router, prefix="/teacher/classes", tags=["教师-班级管理"])

# --- 教师端 — 作业管理 (功能5) ✅ 已激活 ---
api_router.include_router(teacher_assignments_router, prefix="/teacher/assignments", tags=["教师-作业管理"])

# --- 学生端 — 班级 (功能4) ✅ 已激活 ---
api_router.include_router(student_classes_router, prefix="/student/classes", tags=["学生-班级"])

# --- 学生端 — 作业 (功能5) ✅ 已激活 ---
api_router.include_router(student_assignments_router, prefix="/student/assignments", tags=["学生-作业"])


# ============================================================
# 健康检查（基础层自带）
# ============================================================
@api_router.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "service": "ZhiYi API"}
