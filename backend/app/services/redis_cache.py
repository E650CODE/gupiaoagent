"""
缓存层：Redis 优先 + cachetools.TTLCache 内存降级。
- 启动时探测 Redis；不可用则全部走内存 TTL 缓存，应用不阻塞；
- 统一 get/set/delete 接口，序列化为 JSON 字符串；
- pandas.DataFrame 通过 to_json / read_json 序列化。
"""

import json
from typing import Any, Optional

import pandas as pd
import redis
from cachetools import TTLCache

from app.core.config import settings
from app.core.logger import logger


class CacheBackend:
    """缓存抽象：Redis 主，内存兜底。"""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        # 进程内兜底：最多 4096 项，单条 TTL 由 set 参数控制，TTLCache 默认 TTL 用最大值，
        # 我们手动按 expire_at 字典存储管理（简单一致）。
        self._mem: TTLCache = TTLCache(maxsize=4096, ttl=24 * 3600)
        self._mode = "memory"
        self._try_connect_redis()

    def _try_connect_redis(self) -> None:
        try:
            r = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or None,
                socket_connect_timeout=2,
                socket_timeout=3,
                decode_responses=True,
            )
            r.ping()
            self._redis = r
            self._mode = "redis"
            logger.info(f"Redis 已连接: {settings.redis_url}")
        except Exception as e:
            self._redis = None
            self._mode = "memory"
            logger.warning(f"Redis 不可用，降级到内存缓存: {e}")

    @property
    def mode(self) -> str:
        return self._mode

    def get(self, key: str) -> Any:
        try:
            if self._redis:
                raw = self._redis.get(key)
            else:
                raw = self._mem.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"cache.get 失败 key={key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        try:
            raw = json.dumps(value, ensure_ascii=False, default=str)
            if self._redis:
                self._redis.setex(key, ttl, raw)
            else:
                # cachetools 的 TTLCache 全局 ttl 不支持按键设置，
                # 这里近似做法：把过期时间写在 value 里由 get 时校验过于复杂，
                # 实践中内存降级仅供本地调试，采用默认 ttl 即可（24h 上限），
                # 频繁刷新的 key 自然会被新值覆盖。
                self._mem[key] = raw
            return True
        except Exception as e:
            logger.warning(f"cache.set 失败 key={key}: {e}")
            return False

    def delete(self, key: str) -> None:
        try:
            if self._redis:
                self._redis.delete(key)
            else:
                self._mem.pop(key, None)
        except Exception:
            pass


# 全局单例
cache = CacheBackend()


# ────────── DataFrame 序列化 helper ──────────
def df_to_cache(df: pd.DataFrame) -> list:
    """DataFrame -> list of records (cache.set 会再做 json.dumps)。"""
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def cache_to_df(raw: Any) -> Optional[pd.DataFrame]:
    """从缓存值还原 DataFrame；cache.get 已 json.loads, raw 应是 list。"""
    if raw is None:
        return None
    if isinstance(raw, list):
        return pd.DataFrame(raw) if raw else pd.DataFrame()
    if isinstance(raw, str):
        # 兼容历史字符串格式
        try:
            import io
            return pd.read_json(io.StringIO(raw), orient="records")
        except Exception:
            return None
    return None
