"""API 路由聚合 — 所有 v1 路由在此注册"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.agent import router as agent_router
from app.api.v1.summary import router as summary_router
from app.api.v1.exercises import router as exercises_router
from app.api.v1.files import router as files_router
from app.api.v1.knowledge import router as knowledge_router

api_router = APIRouter(prefix="/api/v1")

# ── 健康检查 ──
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "ZhiYi API", "version": "1.0.0"}

# ── 注册子路由 ──
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(users_router, prefix="/users", tags=["用户"])
api_router.include_router(agent_router, prefix="/agent", tags=["AI Agent"])
api_router.include_router(summary_router, prefix="/summaries", tags=["课文总结"])
api_router.include_router(exercises_router, prefix="/exercises", tags=["习题"])
api_router.include_router(files_router, prefix="/files", tags=["文件管理"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识图谱"])
