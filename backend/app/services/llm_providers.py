"""
Provider 适配层。
不同厂商的差异仅在：base_url / list_models 路径 / 鉴权头格式。
本项目仅需 OpenAI 兼容协议，火山方舟与 DeepSeek 都符合，因此用统一 OpenAI Schema。
"""

from typing import Iterable

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import LLMRequestError
from app.core.logger import logger


# 各 provider 的 list_models 端点（OpenAI 协议统一为 GET /models）
_LIST_MODELS_PATH = {
    "volcengine": "/models",
    "deepseek": "/models",
    "openai_compatible": "/models",
}


def _norm_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.RequestException,)),
    reraise=True,
)
def list_models(provider: str, base_url: str, api_key: str, timeout: int = 15) -> list[str]:
    """
    自动拉取该 provider+key 支持的模型列表。
    返回模型 id 列表（按字母排序）。
    """
    if not base_url or not api_key:
        raise LLMRequestError("base_url 或 api_key 为空，无法拉取模型列表")
    path = _LIST_MODELS_PATH.get(provider, "/models")
    url = f"{_norm_base_url(base_url)}{path}"
    logger.info(f"GET {url} (list_models, provider={provider})")
    try:
        resp = requests.get(url, headers=_auth_headers(api_key), timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"list_models 失败: {e}")
        raise
    payload = resp.json()
    # OpenAI 标准: {"data":[{"id":"..."},...]}
    items: Iterable = payload.get("data") or payload.get("models") or []
    ids = []
    for it in items:
        if isinstance(it, dict):
            mid = it.get("id") or it.get("name") or it.get("model")
            if mid:
                ids.append(str(mid))
        elif isinstance(it, str):
            ids.append(it)
    return sorted(set(ids))
