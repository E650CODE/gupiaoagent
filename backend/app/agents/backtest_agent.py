"""
回测 Agent。
本地段: 调用回测引擎执行模拟交易, 计算核心指标;
AI 段: 调 LLM 输出策略评估、优缺点、优化建议。
"""

import asyncio
from typing import Any

from app.agents.base import BaseAgent
from app.agents.data_agent import DataAgent
from app.agents.factor_agent import FactorAgent
# 触发引擎注册
from app.backtest import engine_simple  # noqa: F401
from app.backtest.engine_base import get_engine
from app.core.exceptions import InvalidParamError
from app.core.logger import logger
from app.services import llm_client, sqlite_store
from app.utils.prompt_templates import BACKTEST_SYSTEM, backtest_user_prompt


class BacktestAgent(BaseAgent):
    name = "backtest"

    def __init__(self, data_agent: DataAgent | None = None, factor_agent: FactorAgent | None = None):
        self.data_agent = data_agent or DataAgent()
        self.factor_agent = factor_agent or FactorAgent()

    async def _handle(self, payload: dict) -> Any:
        return await self.run_backtest(
            strategy=payload.get("strategy", "ma_bull"),
            start=payload.get("start"),
            end=payload.get("end"),
            universe=payload.get("universe"),
            params=payload.get("params") or {},
            engine_key=payload.get("engine", "simple"),
            enable_ai=bool(payload.get("enable_ai", True)),
        )

    async def run_backtest(
        self,
        strategy: str,
        start: str,
        end: str,
        universe: list[str] | None = None,
        params: dict | None = None,
        engine_key: str = "simple",
        enable_ai: bool = True,
    ) -> dict:
        if not start or not end:
            raise InvalidParamError("start / end 必填 (格式 YYYYMMDD)")

        engine = get_engine(engine_key)
        logger.info(f"[backtest] 启动引擎 {engine_key} strategy={strategy} {start}~{end}")

        result = await engine.run(
            strategy_key=strategy,
            start=start,
            end=end,
            kline_provider=self.data_agent.get_kline,
            factor_calculator=self.factor_agent.calc_all,
            universe=universe,
            params=params,
        )

        # 持久化到 SQLite
        try:
            sqlite_store.save_backtest_record(
                strategy=strategy, start=start, end=end,
                params=params or {}, result=result.metrics, nav=result.nav_curve,
            )
        except Exception as e:
            logger.warning(f"[backtest] 保存记录失败: {e}")

        # LLM 总结
        ai_summary = None
        if enable_ai and result.metrics and "error" not in result.metrics:
            try:
                user_prompt = backtest_user_prompt(
                    strategy=strategy, params=params or {},
                    metrics=result.metrics, period=f"{start}~{end}",
                )
                ai_summary = await asyncio.to_thread(
                    llm_client.chat, "backtest", BACKTEST_SYSTEM, user_prompt, json_mode=True
                )
            except Exception as e:
                logger.warning(f"[backtest] LLM 总结失败: {e}")
                ai_summary = {"error": str(e)}

        return {
            "strategy": strategy,
            "engine": engine_key,
            "period": f"{start}~{end}",
            "metrics": result.metrics,
            "nav_curve": result.nav_curve,
            "trades": result.trades,
            "ai_summary": ai_summary,
            "disclaimer": "本内容仅为数据分析学习，不构成投资建议",
        }
