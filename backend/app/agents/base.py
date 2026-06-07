"""
Agent 抽象基类。
统一 handle(payload) -> AgentResult 接口；
为子 Agent 提供通用日志、计时、错误兜底。
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import AgentExecutionError, AgentTimeoutError
from app.core.logger import logger


@dataclass
class AgentResult:
    """统一返回结构。"""
    ok: bool = True
    data: Any = None
    error: str | None = None
    elapsed_ms: int = 0
    agent: str = ""
    extra: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """Agent 基类。子类实现 _handle(payload)，外部统一调 handle()。"""

    name: str = "base"

    @abstractmethod
    async def _handle(self, payload: dict) -> Any:
        ...

    async def handle(self, payload: dict, timeout: int = 60) -> AgentResult:
        """带超时与错误兜底的对外入口。"""
        t0 = time.time()
        try:
            data = await asyncio.wait_for(self._handle(payload or {}), timeout=timeout)
            elapsed = int((time.time() - t0) * 1000)
            logger.info(f"[{self.name}] ok in {elapsed}ms")
            return AgentResult(ok=True, data=data, elapsed_ms=elapsed, agent=self.name)
        except asyncio.TimeoutError:
            elapsed = int((time.time() - t0) * 1000)
            logger.error(f"[{self.name}] timeout after {elapsed}ms")
            return AgentResult(
                ok=False, error=f"{self.name} 超时 ({timeout}s)",
                elapsed_ms=elapsed, agent=self.name,
            )
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            logger.exception(f"[{self.name}] error: {e}")
            return AgentResult(
                ok=False, error=f"{type(e).__name__}: {e}",
                elapsed_ms=elapsed, agent=self.name,
            )
