"""
统一异常体系。
所有业务/数据/LLM 异常继承 AppException；
全局 ExceptionHandler 把任何异常包装成 {code, msg, trace_id, disclaimer} 返回。
"""

from typing import Any


class AppException(Exception):
    """业务异常基类。code 业务错误码；msg 用户友好提示；detail 调试信息。"""

    code: int = 1000
    msg: str = "应用异常"

    def __init__(self, msg: str | None = None, detail: Any = None, code: int | None = None):
        self.msg = msg or self.msg
        self.detail = detail
        if code is not None:
            self.code = code
        super().__init__(self.msg)


# ─── 数据层 ───
class DataSourceError(AppException):
    code = 2001
    msg = "数据源接口异常"


class DataNotFoundError(AppException):
    code = 2002
    msg = "数据未找到"


# ─── 缓存层 ───
class CacheError(AppException):
    code = 2101
    msg = "缓存读写异常"


# ─── LLM ───
class LLMConfigError(AppException):
    code = 3001
    msg = "大模型配置错误"


class LLMRequestError(AppException):
    code = 3002
    msg = "大模型请求失败"


class LLMResponseParseError(AppException):
    code = 3003
    msg = "大模型返回解析失败"


# ─── Agent ───
class AgentTimeoutError(AppException):
    code = 4001
    msg = "Agent 执行超时"


class AgentExecutionError(AppException):
    code = 4002
    msg = "Agent 执行失败"


# ─── 参数 ───
class InvalidParamError(AppException):
    code = 4400
    msg = "请求参数无效"


# ═══════════════════════════════════════════════════════════════
# FastAPI 全局异常处理器
# 注册到 app 后，所有异常最终以统一格式返回前端：
#   { code, msg, trace_id, data, disclaimer }
# ═══════════════════════════════════════════════════════════════

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import get_trace_id, logger


def _error_response(code: int, msg: str, detail: Any = None) -> JSONResponse:
    data = {"detail": str(detail)} if detail else {}
    return JSONResponse(
        status_code=200,  # 统一 200，业务错误通过 code 字段区分
        content={
            "code": code,
            "msg": msg,
            "trace_id": get_trace_id(),
            "data": data,
            "disclaimer": settings.DISCLAIMER,
        },
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """捕获 AppException 及其子类。"""
    logger.warning(f"业务异常 [{exc.code}] {exc.msg} | detail={exc.detail}")
    return _error_response(exc.code, exc.msg, exc.detail)


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """捕获 Starlette/FastAPI HTTPException（如 404/422）。"""
    code = exc.status_code
    detail = exc.detail if hasattr(exc, "detail") else str(exc)
    logger.warning(f"HTTP {code}: {detail}")
    # 422 等前端校验错误给更人性化的 msg
    msg = "请求参数校验失败" if code == 422 else f"HTTP {code}"
    return _error_response(code, msg, detail)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """最终兜底：未预期的异常。"""
    logger.exception(f"未捕获异常: {exc}")
    return _error_response(5000, "服务器内部错误", str(exc))