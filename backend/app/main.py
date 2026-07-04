"""
智翼（ZhiYi）AI 学习助手平台 — FastAPI 应用入口

启动方式:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis import close_redis
from app.middleware.cors import setup_cors
from app.middleware.logging import setup_logging_middleware
from app.schemas.common import ErrorCode


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    yield
    # 关闭时：释放 Redis 连接
    await close_redis()


def create_app() -> FastAPI:
    """工厂函数：创建并配置 FastAPI 应用"""
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        description="智翼 AI 学习助手平台后端服务",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 中间件
    setup_cors(app)
    setup_logging_middleware(app)

    # 统一异常处理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "服务器内部错误",
                "detail": str(exc) if settings.DEBUG else None,
            },
        )

    # 路由
    app.include_router(api_router)

    return app


app = create_app()
