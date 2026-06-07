"""
全局日志模块。
基于 loguru：控制台 + 按日切割文件；通过 contextvar 注入 trace_id 贯穿请求链路。
"""

import sys
import uuid
from contextvars import ContextVar
from pathlib import Path

from loguru import logger

from app.core.config import settings


# ─── trace_id 上下文 ───
_trace_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def set_trace_id(trace_id: str | None = None) -> str:
    """设置当前请求的 trace_id；不传则自动生成。"""
    tid = trace_id or uuid.uuid4().hex[:12]
    _trace_ctx.set(tid)
    return tid


def get_trace_id() -> str:
    """读取当前 trace_id；未设置返回 '-'。"""
    return _trace_ctx.get()


def _patcher(record: dict) -> None:
    """loguru patcher：把 trace_id 注入到 record['extra']。"""
    record["extra"]["trace_id"] = get_trace_id()


def setup_logger() -> None:
    """初始化日志：去除默认 handler，按需添加控制台+文件。重复调用安全。"""
    logger.remove()
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[trace_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    # 控制台
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=log_format,
        backtrace=True,
        diagnose=False,  # 生产关闭以免泄露变量
    )
    # 文件（按日切割，保留 14 天）
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        format=log_format,
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,  # 多进程安全
    )
    # LLM 调用单独落盘（按 trace_id 检索方便）
    logger.add(
        log_dir / "llm_{time:YYYY-MM-DD}.log",
        level="INFO",
        format=log_format,
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,
        filter=lambda r: r["extra"].get("category") == "llm",
    )
    # 注入 trace_id
    logger.configure(patcher=_patcher)


__all__ = ["logger", "setup_logger", "set_trace_id", "get_trace_id"]