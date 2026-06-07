"""
全局唯一的 LLM HTTP 客户端，所有 Agent 通过 llm_client.chat(agent_name, ...) 调用。
- 兼容 OpenAI ChatCompletion 协议（火山方舟/DeepSeek 都符合）；
- 自动从 llm_config_store 取该 Agent 的配置；
- tenacity 3 次指数退避重试；
- json_mode=True 时强制 JSON 返回并容错解析。
"""

import json
import re
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import LLMRequestError, LLMResponseParseError
from app.core.logger import logger
from app.services.llm_config_store import get_agent_config


class _LLMException(Exception):
    """内部用：触发 tenacity 重试。"""


def _norm_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((_LLMException, requests.RequestException)),
    reraise=True,
)
def _do_post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    """统一 POST，HTTP 5xx / 网络错误自动重试。"""
    logger.bind(category="llm").info(f"POST {url} payload_keys={list(payload.keys())}")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as e:
        logger.bind(category="llm").warning(f"网络错误: {e}")
        raise
    if resp.status_code >= 500:
        # 5xx 触发重试
        logger.bind(category="llm").warning(f"5xx 响应: {resp.status_code} body={resp.text[:200]}")
        raise _LLMException(f"5xx: {resp.status_code}")
    if resp.status_code >= 400:
        # 4xx 不重试（参数/鉴权问题）
        raise LLMRequestError(
            f"LLM 请求失败 status={resp.status_code}", detail=resp.text[:500]
        )
    try:
        return resp.json()
    except Exception as e:
        raise LLMResponseParseError("响应非 JSON", detail=resp.text[:500])


def _extract_json(text: str) -> Any:
    """从文本中提取首个 JSON 对象。容错处理 ```json ... ``` 包裹。"""
    if not text:
        raise LLMResponseParseError("LLM 返回空文本")
    # 去除 markdown code fence
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.S)
    if m:
        candidate = m.group(1)
    else:
        # 找首个 { ... }
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        candidate = m.group(1) if m else text
    try:
        return json.loads(candidate)
    except Exception as e:
        raise LLMResponseParseError(f"JSON 解析失败: {e}", detail=text[:500])


def chat(
    agent: str,
    system: str,
    user: str,
    json_mode: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Any:
    """
    统一对话入口。
    :param agent: 调用方 Agent 名（selector/predictor/risk/backtest）
    :param system: 系统提示词
    :param user: 用户提示词
    :param json_mode: 是否要求 JSON 返回（True 时返回 dict/list；False 时返回 str）
    :return: 文本或解析后的 JSON 对象
    """
    cfg = get_agent_config(agent)
    url = f"{_norm_base_url(cfg['base_url'])}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature if temperature is not None else cfg.get("temperature", 0.3),
        "max_tokens": max_tokens or cfg.get("max_tokens", 2048),
        "stream": False,
    }
    if json_mode:
        # OpenAI / 火山 / DeepSeek 都支持 response_format
        payload["response_format"] = {"type": "json_object"}

    data = _do_post(url, headers, payload, timeout=cfg.get("timeout", 60))

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMResponseParseError("响应缺少 choices[0].message.content", detail=str(data)[:500])

    logger.bind(category="llm").info(
        f"agent={agent} model={cfg['model']} resp_len={len(text)} usage={data.get('usage')}"
    )

    if json_mode:
        return _extract_json(text)
    return text


def test_connection(provider: str, base_url: str, api_key: str, model: str, timeout: int = 30) -> dict:
    """
    连通性测试：临时构造一次最小 chat 调用。
    返回 {ok: bool, latency_ms: int, sample: str, error: str|None}
    """
    import time

    url = f"{_norm_base_url(base_url)}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "stream": False,
    }
    t0 = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        latency = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            return {"ok": False, "latency_ms": latency, "sample": "", "error": resp.text[:300]}
        data = resp.json()
        sample = data["choices"][0]["message"]["content"][:50]
        return {"ok": True, "latency_ms": latency, "sample": sample, "error": None}
    except Exception as e:
        return {"ok": False, "latency_ms": int((time.time() - t0) * 1000), "sample": "", "error": str(e)}
