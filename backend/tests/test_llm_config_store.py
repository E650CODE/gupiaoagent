"""LLM 配置加解密 + CRUD 单元测试。"""

import os
import sys
import tempfile
from pathlib import Path

# 在导入 app 之前指定一个临时 LLM_CONFIG_PATH
_tmpdir = tempfile.mkdtemp(prefix="llmcfg_test_")
_tmp_path = str(Path(_tmpdir) / "llm.json")
os.environ["LLM_CONFIG_PATH"] = _tmp_path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 强制覆盖 settings (settings 是 lru_cache 单例, 其它测试可能已实例化)
from app.core import config as _cfg  # noqa: E402
_cfg.settings.LLM_CONFIG_PATH = _tmp_path

from app.services import llm_config_store as store  # noqa: E402


def test_encrypt_decrypt_roundtrip():
    raw = "sk-1234567890abcdefg"
    enc = store.encrypt(raw)
    assert enc.startswith("ENC:")
    assert store.decrypt(enc) == raw
    # 幂等
    assert store.encrypt(enc) == enc


def test_mask_key():
    assert store.mask_key("") == ""
    assert store.mask_key("short") == "*****"
    assert store.mask_key("sk-1234567890abcd") == "sk-1****abcd"


def test_load_default_creates_file():
    cfg = store.load_config()
    assert "agents" in cfg
    for agent in store.DEFAULT_AGENTS:
        assert agent in cfg["agents"]


def test_update_agent_config_persist_and_encrypt():
    store.update_agent_config(
        "selector",
        {"base_url": "https://example.com/v1", "api_key": "sk-real-key", "model": "test-model"},
    )
    # 重新读出（解密）
    cfg = store.load_config(decrypt_key=True)
    assert cfg["agents"]["selector"]["api_key"] == "sk-real-key"
    # 文件中应是加密的
    raw_text = Path(os.environ["LLM_CONFIG_PATH"]).read_text(encoding="utf-8")
    assert "sk-real-key" not in raw_text
    assert "ENC:" in raw_text


def test_mask_value_not_overwrite():
    # 模拟前端把掩码值传回来，不应覆盖真实 key
    store.update_agent_config("selector", {"api_key": "sk-r****key"})
    cfg = store.load_config(decrypt_key=True)
    assert cfg["agents"]["selector"]["api_key"] == "sk-real-key"
