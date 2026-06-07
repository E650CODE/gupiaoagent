"""
全局配置模块。
从 .env 加载所有运行参数，使用 pydantic-settings 做校验与类型转换。
首次运行自动生成 LLM_CONFIG_SECRET。
"""

import os
from functools import lru_cache
from pathlib import Path
from cryptography.fernet import Fernet

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有配置集中管理，属性即来自 .env 的同名字段。"""

    # ─── 应用基础 ───
    APP_NAME: str = "gupiaoagent"
    APP_ENV: str = "dev"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000

    # ─── 日志 ───
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    # ─── 数据存储 ───
    DATA_DIR: str = "./data"
    SQLITE_PATH: str = "./data/app.db"

    # ─── Redis ───
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # ─── LLM 配置 ───
    LLM_CONFIG_SECRET: str = ""
    LLM_CONFIG_PATH: str = "./data/llm_config.json"

    # ─── CORS ───
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ─── Agent 调度 ───
    AGENT_TIMEOUT_SECONDS: int = 60
    AGENT_MAX_RETRY: int = 3

    # ─── 合规声明 ───
    DISCLAIMER: str = "本内容仅为数据分析学习，不构成投资建议"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 允许 .env 里有多余变量不报错
    )

    @property
    def redis_url(self) -> str:
        """组装 Redis 连接 URL。"""
        pw = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{pw}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS 字符串 -> 列表"""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def fernet_key(self) -> bytes:
        """返回 Fernet 密钥（bytes）。首次运行自动生成并写回 .env。"""
        if not self.LLM_CONFIG_SECRET:
            key = Fernet.generate_key().decode()
            self._write_env("LLM_CONFIG_SECRET", key)
            object.__setattr__(self, "LLM_CONFIG_SECRET", key)
        return self.LLM_CONFIG_SECRET.encode()

    @staticmethod
    def _write_env(key: str, value: str) -> None:
        """将 key=value 写入 .env 文件（追加或替换）。"""
        env_path = Path(".env")
        if not env_path.exists():
            env_path.write_text(f"{key}={value}\n", encoding="utf-8")
            return
        lines = env_path.read_text(encoding="utf-8").splitlines()
        replaced = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                replaced = True
                break
        if not replaced:
            lines.append(f"{key}={value}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─── 全局单例 ───
@lru_cache()
def get_settings() -> Settings:
    """缓存 settings 避免重复 IO。"""
    return Settings()


settings = get_settings()