"""
趋势预测 Agent。
本地段: 拉 K 线、算因子、整理特征文本;
AI 段: 调 LLM (JSON 模式) 输出方向/概率/价格区间/逻辑。
"""

import asyncio
from typing import Any

from app.agents.base import BaseAgent
from app.agents.data_agent import DataAgent
from app.agents.factor_agent import FactorAgent
from app.core.exceptions import InvalidParamError
from app.core.logger import logger
from app.services import llm_client
from app.utils.prompt_templates import PREDICTOR_SYSTEM, predictor_user_prompt


class PredictorAgent(BaseAgent):
    name = "predictor"

    def __init__(self, data_agent: DataAgent | None = None, factor_agent: FactorAgent | None = None):
        self.data_agent = data_agent or DataAgent()
        self.factor_agent = factor_agent or FactorAgent()

    async def _handle(self, payload: dict) -> Any:
        code = payload.get("code")
        if not code:
            raise InvalidParamError("predictor 需要 code 入参")
        horizon = int(payload.get("horizon_days", 5))
        return await self.predict(code, horizon)

    async def predict(self, code: str, horizon_days: int = 5) -> dict:
        """对单只股票输出 3-10 日趋势预测。"""
        if not 3 <= horizon_days <= 10:
            raise InvalidParamError("horizon_days 必须在 3-10 之间")

        kdf = await self.data_agent.get_kline(code)
        if kdf.empty:
            raise InvalidParamError(f"个股 {code} 无数据")
        fdf = self.factor_agent.calc_all(kdf)
        snapshot = fdf.iloc[-1].to_dict()
        recent_pct = fdf["pct_chg"].dropna().tolist() if "pct_chg" in fdf.columns else []

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

        # AI 段: LLM 调用
        ai_result = None
        try:
            user_prompt = predictor_user_prompt(code, name, snapshot, recent_pct)
            ai_result = await asyncio.to_thread(
                llm_client.chat, "predictor", PREDICTOR_SYSTEM, user_prompt, json_mode=True
            )
        except Exception as e:
            logger.warning(f"[predictor] LLM 调用失败: {e}")
            ai_result = {"error": str(e)}

        # 置信度分级
        prob = (ai_result or {}).get("prob", 0) or 0
        if prob >= 0.7:
            confidence = "高"
        elif prob >= 0.55:
            confidence = "中"
        else:
            confidence = "低"

        return {
            "code": code,
            "name": name,
            "direction": (ai_result or {}).get("direction", "unknown"),
            "prob": prob,
            "price_low": (ai_result or {}).get("price_low"),
            "price_high": (ai_result or {}).get("price_high"),
            "horizon_days": (ai_result or {}).get("horizon_days", horizon_days),
            "reasoning": (ai_result or {}).get("reasoning", ""),
            "risk_warning": (ai_result or {}).get("risk_warning", ""),
            "confidence": confidence,
            "current_price": round(snapshot.get("close", 0), 2),
            "disclaimer": "本内容仅为数据分析学习，不构成投资建议",
        }
