"""
HTTP 中间件：
1) TraceIdMiddleware  — 为每个请求生成 trace_id 并写入响应头；
2) ComplianceMiddleware — 拦截所有 /api/v1/* JSON 响应，强制注入 disclaimer 字段。
"""

import json
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logger import logger, set_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    """为每个请求生成 trace_id 并写入响应头 X-Trace-Id。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 优先复用客户端传过来的 trace_id（便于调用方串联日志）
        tid = request.headers.get("X-Trace-Id") or None
        tid = set_trace_id(tid)
        logger.info(f"→ {request.method} {request.url.path}")
        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception(f"未捕获异常: {e}")
            raise
        response.headers["X-Trace-Id"] = tid
        logger.info(f"← {request.method} {request.url.path} {response.status_code}")
        return response


class ComplianceMiddleware(BaseHTTPMiddleware):
    """
    拦截 /api/v1/* 的 JSON 响应，确保返回体含 `disclaimer` 字段。
    若响应已是统一 envelope（含 code/msg/data）则注入到顶层；
    否则保留原样不强插（如 OpenAPI 文档、静态资源）。
    """

    TARGET_PREFIX = "/api/v1"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        if not request.url.path.startswith(self.TARGET_PREFIX):
            return response
        ctype = response.headers.get("content-type", "")
        if "application/json" not in ctype:
            return response

        # 收集 body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            # 非标准 JSON 不动
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=ctype,
            )

        # 只在 dict 形态注入；list 类型不处理（业务接口都用 envelope）
        if isinstance(payload, dict) and "disclaimer" not in payload:
            payload["disclaimer"] = settings.DISCLAIMER

        new_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = dict(response.headers)
        headers["content-length"] = str(len(new_body))
        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )