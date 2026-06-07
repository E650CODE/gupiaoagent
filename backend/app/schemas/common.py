"""
统一响应模型。所有路由返回 ApiResponse(...) 或 Resp.ok(...)。
合规中间件会确保 disclaimer 字段存在，但路由层主动写明更清晰。
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import get_trace_id

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(0, description="业务码，0=成功")
    msg: str = Field("ok", description="提示信息")
    trace_id: str = Field("-", description="链路追踪ID")
    data: T | None = Field(None, description="业务数据")
    disclaimer: str = Field("", description="合规风险提示")


class Resp:
    """便捷构造器。"""

    @staticmethod
    def ok(data: Any = None, msg: str = "ok") -> dict:
        return {
            "code": 0,
            "msg": msg,
            "trace_id": get_trace_id(),
            "data": data,
            "disclaimer": settings.DISCLAIMER,
        }

    @staticmethod
    def fail(code: int, msg: str, data: Any = None) -> dict:
        return {
            "code": code,
            "msg": msg,
            "trace_id": get_trace_id(),
            "data": data,
            "disclaimer": settings.DISCLAIMER,
        }