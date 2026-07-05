"""
请求日志中间件
"""

import time

from fastapi import FastAPI, Request
from loguru import logger


async def log_request_middleware(request: Request, call_next):
    """记录每个 HTTP 请求的方法、路径和耗时"""
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000  # ms
    logger.info(
        f"{request.method} {request.url.path} | "
        f"status={response.status_code} | "
        f"elapsed={elapsed:.1f}ms"
    )
    return response


def setup_logging_middleware(app: FastAPI) -> None:
    """注册请求日志中间件"""
    app.middleware("http")(log_request_middleware)
