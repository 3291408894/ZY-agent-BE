"""
智翼（ZhiYi）AI 学习助手平台 — FastAPI 应用入口

启动方式:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.redis import close_redis
from app.middleware.cors import setup_cors
from app.middleware.logging import setup_logging_middleware
from app.schemas.common import ErrorCode


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"🚀 {settings.APP_NAME} API 启动中...")
    # 自动建表（免去手动 migration）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ 数据库表已就绪")
    yield
    # 关闭时：释放 Redis 连接
    await close_redis()
    logger.info(f"👋 {settings.APP_NAME} API 已关闭")


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

    # 路由
    app.include_router(api_router)

    # --- 全局异常处理器 ---

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Pydantic 参数校验失败 → 40001"""
        errors = []
        for error in exc.errors():
            field = " → ".join(str(loc) for loc in error["loc"])
            errors.append(f"{field}: {error['msg']}")
        logger.warning(f"参数校验失败 | {request.method} {request.url.path} | {errors}")
        return JSONResponse(
            status_code=400,
            content={
                "code": ErrorCode.PARAM_INVALID,
                "message": "参数校验失败",
                "detail": errors,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTPException → 透传 detail 中的 code/message（已由各路由正确设置）"""
        # 如果 detail 已经是标准格式（dict 带 code），则直接透传
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
            )
        # 否则包装为标准格式
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": str(exc.detail),
                "detail": None,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """未捕获的异常 → 50001"""
        logger.error(f"未处理异常 | {request.method} {request.url.path} | {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "服务器内部错误",
                "detail": str(exc) if settings.DEBUG else None,
            },
        )

    return app


app = create_app()
