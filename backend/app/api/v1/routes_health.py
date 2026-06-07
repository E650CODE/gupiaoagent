"""
健康检查路由。用于联调与运维探活。
"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import Resp

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="服务健康检查")
async def health_check():
    """返回服务基本信息：版本、环境、Redis 配置等（不暴露敏感字段）。"""
    return Resp.ok(
        {
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
            "redis": f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            "status": "up",
        }
    )