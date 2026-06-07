"""
多因子选股 Agent。
本地段: 应用策略筛选 (禁未来函数);
AI 段: 用 LLM 解读选股逻辑、共性特征、板块热度。
"""

import asyncio
from typing import Any

import pandas as pd

from app.agents.base import BaseAgent
from app.agents.data_agent import DataAgent
from app.agents.factor_agent import FactorAgent
from app.core.exceptions import InvalidParamError
from app.core.logger import logger
from app.services import llm_client
from app.strategies.presets import STRATEGY_REGISTRY
from app.utils.prompt_templates import SELECTOR_SYSTEM, selector_user_prompt


class SelectorAgent(BaseAgent):
    name = "selector"

    def __init__(self, data_agent: DataAgent | None = None, factor_agent: FactorAgent | None = None):
        self.data_agent = data_agent or DataAgent()
        self.factor_agent = factor_agent or FactorAgent()

    async def _handle(self, payload: dict) -> Any:
        return await self.select(
            strategies=payload.get("strategies", []),
            universe=payload.get("universe"),
            params=payload.get("params") or {},
            top_n=int(payload.get("top_n", 20)),
            enable_ai=bool(payload.get("enable_ai", True)),
        )

    async def select(
        self,
        strategies: list[str],
        universe: list[str] | None = None,
        params: dict | None = None,
        top_n: int = 20,
        enable_ai: bool = True,
    ) -> dict:
        """
        多策略选股 (AND 组合: 必须同时满足所有指定策略)。
        :param strategies: 策略 key 列表, 必须存在于 STRATEGY_REGISTRY
        :param universe: 限定股票池; 不传则用默认池 (避免全市场卡顿)
        :param params: 策略参数覆盖
        :param top_n: 返回数量上限
        :param enable_ai: 是否调用 LLM 解读
        """
        if not strategies:
            raise InvalidParamError("strategies 不能为空")
        unknown = [s for s in strategies if s not in STRATEGY_REGISTRY]
        if unknown:
            raise InvalidParamError(f"未知策略: {unknown}")

        # 股票池: 不传则用沪深 300 头部样本
        if not universe:
            universe = self._default_universe()
        logger.info(f"[selector] 策略={strategies} 股票池={len(universe)} top_n={top_n}")

        # 1) 并发拉每只股票的 K 线 + 算因子, 取最新一行做筛选
        async def _fetch_one(code: str) -> dict | None:
            try:
                kdf = await self.data_agent.get_kline(code)
                if kdf.empty or len(kdf) < 60:
                    return None
                fdf = self.factor_agent.calc_all(kdf)
                if fdf.empty:
                    return None
                last = fdf.iloc[-1].to_dict()
                last["code"] = code
                return last
            except Exception as e:
                logger.warning(f"[selector] {code} 拉取失败: {e}")
                return None

        rows = await asyncio.gather(*[_fetch_one(c) for c in universe])
        rows = [r for r in rows if r is not None]

        # 2) 应用每个策略, AND 组合
        candidates = []
        for row in rows:
            ok = True
            for sk in strategies:
                check = STRATEGY_REGISTRY[sk]["check"]
                sparam = {**STRATEGY_REGISTRY[sk].get("params", {}), **(params or {})}
                try:
                    if not check(row, sparam):
                        ok = False
                        break
                except Exception as e:
                    logger.warning(f"[selector] {row.get('code')} 策略 {sk} 异常: {e}")
                    ok = False
                    break
            if ok:
                candidates.append(row)

        # 3) 补名称 (从股票列表查)
        stock_df = await self.data_agent.get_all_stocks()
        name_map = dict(zip(stock_df["code"], stock_df["name"])) if not stock_df.empty else {}
        for c in candidates:
            c["name"] = name_map.get(c["code"], "")

        # 4) 二次过滤: 已在 data_filter 过滤了 ST, 这里再排掉名字带 ST 的兜底
        candidates = [c for c in candidates if "ST" not in (c.get("name") or "").upper()]

        # 5) 按量比+涨幅排序, 取 top_n
        candidates.sort(
            key=lambda x: (x.get("vol_ratio") or 0) * 0.5 + (x.get("pct_chg") or 0) * 0.5,
            reverse=True,
        )
        top = candidates[:top_n]
        logger.info(f"[selector] 候选 {len(candidates)} -> 取前 {len(top)}")

        # 6) 选股结果整理: 只输出关键字段
        result_stocks = [
            {
                "code": c["code"],
                "name": c.get("name", ""),
                "close": round(c.get("close", 0), 2),
                "pct_chg": round(c.get("pct_chg", 0), 2),
                "ma5": round(c.get("ma5", 0), 2),
                "ma20": round(c.get("ma20", 0), 2),
                "macd_dif": round(c.get("macd_dif", 0), 3),
                "rsi6": round(c.get("rsi6", 0), 1),
                "vol_ratio": round(c.get("vol_ratio", 0), 2),
            }
            for c in top
        ]

        # 7) AI 解读
        ai_explanation = None
        if enable_ai and result_stocks:
            rules_txt = [STRATEGY_REGISTRY[s]["desc"] for s in strategies]
            try:
                user_prompt = selector_user_prompt(rules_txt, result_stocks)
                ai_explanation = await asyncio.to_thread(
                    llm_client.chat, "selector", SELECTOR_SYSTEM, user_prompt, json_mode=True
                )
            except Exception as e:
                logger.warning(f"[selector] LLM 解读失败: {e}")
                ai_explanation = {"error": str(e)}

        return {
            "strategies": strategies,
            "rules": [STRATEGY_REGISTRY[s]["desc"] for s in strategies],
            "stocks": result_stocks,
            "count": len(result_stocks),
            "ai_explanation": ai_explanation,
            "disclaimer": "本内容仅为数据分析学习，不构成投资建议",
        }

    @staticmethod
    def _default_universe() -> list[str]:
        return [
            "600519", "601318", "600036", "000858", "000333",
            "600276", "601166", "002594", "000651", "600030",
            "601012", "002415", "300750", "600887", "000725",
            "601398", "601628", "601988", "601857", "600028",
        ]