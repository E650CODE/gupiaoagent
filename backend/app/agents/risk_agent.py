"""
风控评估 Agent。
本地段: 基于规则评级 (高/中/低);
AI 段: 调 LLM 输出风险点解读、止盈止损参考、持仓提示。
"""

import asyncio
from typing import Any

import numpy as np

from app.agents.base import BaseAgent
from app.agents.data_agent import DataAgent
from app.agents.factor_agent import FactorAgent
from app.core.exceptions import InvalidParamError
from app.core.logger import logger
from app.services import llm_client
from app.utils.prompt_templates import RISK_SYSTEM, risk_user_prompt


class RiskAgent(BaseAgent):
    name = "risk"

    def __init__(self, data_agent: DataAgent | None = None, factor_agent: FactorAgent | None = None):
        self.data_agent = data_agent or DataAgent()
        self.factor_agent = factor_agent or FactorAgent()

    async def _handle(self, payload: dict) -> Any:
        code = payload.get("code")
        if not code:
            raise InvalidParamError("risk 需要 code 入参")
        return await self.assess(code)

    async def assess(self, code: str) -> dict:
        """对单只股票做风险评级。"""
        kdf = await self.data_agent.get_kline(code)
        if kdf.empty:
            raise InvalidParamError(f"个股 {code} 无数据")
        fdf = self.factor_agent.calc_all(kdf)
        snapshot = fdf.iloc[-1].to_dict()
        recent_pct = fdf["pct_chg"].dropna().tolist() if "pct_chg" in fdf.columns else []

        # 1) 本地规则评级
        local_level = self._local_rule(fdf, snapshot, recent_pct)
        logger.info(f"[risk] {code} 本地评级={local_level}")

        # 查股票名
        try:
            stocks = await self.data_agent.get_all_stocks()
            name = ""
            if not stocks.empty:
                hit = stocks[stocks["code"] == code]
                if not hit.empty:
                    name = str(hit.iloc[0]["name"])
        except Exception:
            name = ""

        # 2) LLM 风险文案
        ai_result = None
        try:
            user_prompt = risk_user_prompt(code, name, snapshot, local_level, recent_pct)
            ai_result = await asyncio.to_thread(
                llm_client.chat, "risk", RISK_SYSTEM, user_prompt, json_mode=True
            )
        except Exception as e:
            logger.warning(f"[risk] LLM 失败: {e}")
            ai_result = {"error": str(e)}

        return {
            "code": code,
            "name": name,
            "risk_level": local_level,
            "risk_points": (ai_result or {}).get("risk_points", []),
            "stop_profit": (ai_result or {}).get("stop_profit"),
            "stop_loss": (ai_result or {}).get("stop_loss"),
            "advice": (ai_result or {}).get("advice", ""),
            "current_price": round(snapshot.get("close", 0), 2),
            "disclaimer": "本内容仅为数据分析学习，不构成投资建议",
        }

    @staticmethod
    def _local_rule(fdf, snapshot, recent_pct) -> str:
        """本地评级规则: 振幅 / 连续下跌 / 高位放量滞涨 / 资金净流出。"""
        # 近 20 日最高/最低 振幅
        recent = fdf.tail(20)
        if not recent.empty:
            amplitude = (recent["high"].max() - recent["low"].min()) / recent["low"].min() if recent["low"].min() > 0 else 0
        else:
            amplitude = 0
        # 连续 3 日跌幅
        last3 = recent_pct[-3:] if len(recent_pct) >= 3 else recent_pct
        cont_down = all(p < -5 for p in last3) if last3 else False
        # 高位放量滞涨: 涨幅 < 1% 但 量比 > 2
        vol_ratio = snapshot.get("vol_ratio", 0) or 0
        last_pct = recent_pct[-1] if recent_pct else 0
        stagnation = vol_ratio > 2 and 0 < last_pct < 1

        if amplitude > 0.30 or cont_down or stagnation:
            return "高"
        if amplitude > 0.15:
            return "中"
        return "低"
