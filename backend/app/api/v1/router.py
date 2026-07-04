"""
API v1 路由聚合 — 按文档规范组织所有子路由
"""

from fastapi import APIRouter

# ============================================================
# 导入各模块路由（初期先占位导入，模块开发时逐个取消注释）
# ============================================================
# from app.api.v1.auth import router as auth_router
# from app.api.v1.users import router as users_router
# from app.api.v1.agent import router as agent_router
# from app.api.v1.summary import router as summary_router
# from app.api.v1.exercises import router as exercises_router
from app.api.v1.files import router as files_router
# from app.api.v1.knowledge import router as knowledge_router

api_router = APIRouter(prefix="/api/v1")

# --- 认证模块 (PBI_01) ---
# api_router.include_router(auth_router, prefix="/auth", tags=["认证"])

# --- 用户模块 (PBI_01) ---
# api_router.include_router(users_router, prefix="/users", tags=["用户"])

# --- AI Agent 模块 (PBI_04, PBI_12) ---
# api_router.include_router(agent_router, prefix="/agent", tags=["AI Agent"])

# --- 课文总结模块 (PBI_06) ---
# api_router.include_router(summary_router, prefix="/summaries", tags=["课文总结"])

# --- 习题模块 (PBI_08, PBI_09, PBI_10) ---
# api_router.include_router(exercises_router, prefix="/exercises", tags=["习题"])

# --- 文件管理模块 (PBI_05) ---
api_router.include_router(files_router, prefix="/files", tags=["文件管理"])

# --- 知识图谱模块 (PBI_11) ---
# api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识图谱"])


# ============================================================
# 健康检查（基础层自带）
# ============================================================
@api_router.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "service": "ZhiYi API"}
