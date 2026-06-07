"""
LLM 配置持久化。
- 全部 Agent 的模型配置存 backend/data/llm_config.json；
- api_key 字段 Fernet 加密落盘（前缀 ENC: 标识）；
- 读出供后端使用时自动解密；
- 提供 mask_key() 给前端 GET 接口返回掩码值，避免泄漏。
"""

import json
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import LLMConfigError
from app.core.logger import logger

_lock = Lock()

# 需要 LLM 能力的 Agent
DEFAULT_AGENTS = ["selector", "predictor", "risk", "backtest"]

# 内置 provider 模板（前端下拉用）
PROVIDER_PRESETS = {
    "volcengine": {"name": "火山方舟", "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1"},
    "openai_compatible": {"name": "OpenAI 兼容（通用）", "base_url": ""},
}

ENC_PREFIX = "ENC:"


def _fernet() -> Fernet:
    try:
        return Fernet(settings.fernet_key)
    except Exception as e:
        raise LLMConfigError("Fernet 密钥无效", detail=str(e))


def encrypt(plain: str) -> str:
    """加密 api_key，返回 ENC: 前缀字符串。空串不加密。"""
    if not plain:
        return ""
    if plain.startswith(ENC_PREFIX):
        return plain
    token = _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
    return f"{ENC_PREFIX}{token}"


def decrypt(stored: str) -> str:
    """解密 api_key。无前缀视为明文（兼容性）。"""
    if not stored:
        return ""
    if not stored.startswith(ENC_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(ENC_PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise LLMConfigError("api_key 解密失败，可能更换了 LLM_CONFIG_SECRET", detail=str(e))


def mask_key(plain_or_enc: str) -> str:
    """给前端展示用的掩码值，如 sk-1234****abcd。"""
    if not plain_or_enc:
        return ""
    real = decrypt(plain_or_enc) if plain_or_enc.startswith(ENC_PREFIX) else plain_or_enc
    if len(real) <= 8:
        return "*" * len(real)
    return f"{real[:4]}****{real[-4:]}"


def _default_agent_cfg() -> dict:
    return {
        "provider": "deepseek",
        "base_url": "",
        "api_key": "",
        "model": "",
        "timeout": settings.AGENT_TIMEOUT_SECONDS,
        "temperature": 0.3,
        "max_tokens": 2048,
    }


def _default_config() -> dict:
    return {"agents": {agent: _default_agent_cfg() for agent in DEFAULT_AGENTS}}


def load_config(decrypt_key: bool = True) -> dict:
    """加载配置。decrypt_key=False 时保留 ENC: 形式（便于回写）。"""
    path = Path(settings.LLM_CONFIG_PATH)
    if not path.exists():
        cfg = _default_config()
        save_config(cfg)
        return cfg
    with _lock:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.setdefault("agents", {})
    for agent in DEFAULT_AGENTS:
        if agent not in cfg["agents"]:
            cfg["agents"][agent] = _default_agent_cfg()
    if decrypt_key:
        for agent_cfg in cfg["agents"].values():
            agent_cfg["api_key"] = decrypt(agent_cfg.get("api_key", ""))
    return cfg


def save_config(cfg: dict) -> None:
    """保存配置，自动加密所有 agent 的 api_key。"""
    path = Path(settings.LLM_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    to_save = json.loads(json.dumps(cfg))
    for agent_cfg in to_save.get("agents", {}).values():
        agent_cfg["api_key"] = encrypt(agent_cfg.get("api_key", ""))
    with _lock:
        path.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"LLM 配置已保存: {path}")


def update_agent_config(agent: str, patch: dict) -> dict:
    """部分更新某个 Agent 的配置。"""
    if agent not in DEFAULT_AGENTS:
        raise LLMConfigError(f"未知 Agent: {agent}")
    cfg = load_config(decrypt_key=True)
    cur = cfg["agents"].get(agent, _default_agent_cfg())
    allowed = {"provider", "base_url", "api_key", "model", "timeout", "temperature", "max_tokens"}
    for k, v in patch.items():
        if k in allowed and v is not None:
            # 收到的是掩码值则不覆盖（避免把界面回显当作新值存回）
            if k == "api_key" and isinstance(v, str) and "****" in v:
                continue
            cur[k] = v
    cfg["agents"][agent] = cur
    save_config(cfg)
    return cur


def get_agent_config(agent: str) -> dict:
    """获取指定 Agent 的解密后配置。缺关键字段会抛 LLMConfigError。"""
    cfg = load_config(decrypt_key=True)
    agent_cfg = cfg["agents"].get(agent)
    if not agent_cfg:
        raise LLMConfigError(f"未配置 Agent: {agent}")
    missing = [k for k in ("base_url", "api_key", "model") if not agent_cfg.get(k)]
    if missing:
        raise LLMConfigError(f"Agent [{agent}] 缺少必填项: {missing}")
    return agent_cfg


def list_config_masked() -> dict:
    """供前端 GET 用：返回各 Agent 配置，api_key 已掩码。"""
    cfg = load_config(decrypt_key=False)
    out = {"agents": {}, "providers": PROVIDER_PRESETS}
    for agent, c in cfg["agents"].items():
        out["agents"][agent] = {**c, "api_key": mask_key(c.get("api_key", ""))}
    return out
