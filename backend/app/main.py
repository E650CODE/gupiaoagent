"""
FastAPI 应用入口。
启动顺序：日志初始化 → 加载配置 → 注册路由 → 注册中间件 → 注册异常处理器。

启动命令：
    cd backend
    .venv/Scripts/activate   (Windows: source .venv/Scripts/activate)
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import routes_backtest, routes_health, routes_llm, routes_stock
from app.core.config import settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from app.core.logger import logger, setup_logger
from app.core.middleware import ComplianceMiddleware, TraceIdMiddleware
from app.services import sqlite_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启停生命周期。"""
    setup_logger()
    logger.info(f"应用启动: {settings.APP_NAME} | env={settings.APP_ENV}")
    logger.info(f"监听: http://{settings.APP_HOST}:{settings.APP_PORT}")
    logger.info(f"CORS 放行: {settings.cors_origins_list}")
    # 触发 fernet_key 生成（若未初始化）
    _ = settings.fernet_key
    # 初始化 SQLite 表
    sqlite_store.init_db()
    yield
    logger.info("应用关闭")


def create_app() -> FastAPI:
    """工厂方法，便于测试时构造独立 app。"""
    app = FastAPI(
        title="A股智能选股+股价趋势预测系统",
        version="1.0.0",
        description=(
            "**合规声明**：本系统所有页面、接口返回内容仅为数据分析学习用途，"
            "不构成投资建议。"
        ),
        lifespan=lifespan,
    )

    # ─── 中间件（注意：FastAPI 中后注册的先执行，故顺序：合规 → trace_id → cors）───
    app.add_middleware(ComplianceMiddleware)
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )

    # ─── 异常处理器 ───
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ─── 路由 ───
    app.include_router(routes_health.router, prefix="/api/v1")
    app.include_router(routes_llm.router, prefix="/api/v1")
    app.include_router(routes_stock.router, prefix="/api/v1")
    app.include_router(routes_backtest.router, prefix="/api/v1")

    return app


app = create_app()