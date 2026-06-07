"""
主调度 Agent.
三类核心业务: 选股/趋势预测/回测; 外加辅助接口: 个股详情.
异常兜底: 任一子 Agent 失败返回 partial=True.
"""

import asyncio
from app.agents.backtest_agent import BacktestAgent
from app.agents.base import AgentResult
from app.agents.data_agent import DataAgent
from app.agents.factor_agent import FactorAgent
from app.agents.predictor_agent import PredictorAgent
from app.agents.risk_agent import RiskAgent
from app.agents.selector_agent import SelectorAgent
from app.core.config import settings
from app.core.logger import logger


class MasterAgent:
    def __init__(self):
        self.data_agent = DataAgent()
        self.factor_agent = FactorAgent()
        self.selector_agent = SelectorAgent(self.data_agent, self.factor_agent)
        self.predictor_agent = PredictorAgent(self.data_agent, self.factor_agent)
        self.risk_agent = RiskAgent(self.data_agent, self.factor_agent)
        self.backtest_agent = BacktestAgent(self.data_agent, self.factor_agent)
        self.timeout = settings.AGENT_TIMEOUT_SECONDS

    async def handle_select(self, payload: dict) -> dict:
        logger.info(f"[master] handle_select")
        sel = await self.selector_agent.handle(payload, timeout=self.timeout)
        if not sel.ok:
            return {"stage": "selector_failed", "error": sel.error, "partial": True}
        out = sel.data
        if payload.get("enable_risk", True) and out.get("stocks"):
            tasks = [self.risk_agent.handle({"code": s["code"]}, timeout=self.timeout) for s in out["stocks"][:10]]
            risks = await asyncio.gather(*tasks, return_exceptions=True)
            risk_map = {}
            for r in risks:
                if isinstance(r, AgentResult) and r.ok and r.data:
                    risk_map[r.data["code"]] = r.data
            filtered = []
            for s in out["stocks"]:
                r = risk_map.get(s["code"], {})
                s["risk_level"] = r.get("risk_level", "未评估")
                s["risk_points"] = r.get("risk_points", [])[:3]
                if s["risk_level"] != "高":
                    filtered.append(s)
            out["stocks"] = filtered
            out["count"] = len(filtered)
        return out

    async def handle_predict(self, payload: dict) -> dict:
        logger.info(f"[master] handle_predict")
        pred = self.predictor_agent.handle(payload, timeout=self.timeout)
        risk = self.risk_agent.handle({"code": payload.get("code")}, timeout=self.timeout)
        pred_r, risk_r = await asyncio.gather(pred, risk)
        return {"code": payload.get("code"),
                "prediction": pred_r.data if pred_r.ok else {"error": pred_r.error},
                "risk": risk_r.data if risk_r.ok else {"error": risk_r.error},
                "partial": not (pred_r.ok and risk_r.ok)}

    async def handle_backtest(self, payload: dict) -> dict:
        logger.info(f"[master] handle_backtest")
        bt = await self.backtest_agent.handle(payload, timeout=self.timeout * 5)
        return bt.data if bt.ok else {"error": bt.error, "partial": True}

    async def handle_detail(self, code: str, refresh: bool = False) -> dict:
        logger.info(f"[master] handle_detail {code}")
        kdf = await self.data_agent.get_kline(code)
        if kdf.empty:
            return {"error": f"{code} 无数据", "partial": True}
        fdf = self.factor_agent.calc_all(kdf)
        kline_json = kdf.to_dict(orient="records")
        factors_json = fdf.to_dict(orient="records")
        funds = {}
        try:
            funds = await self.data_agent.get_money_flow(code)
            funds = funds.to_dict(orient="records")
        except Exception:
            pass
        return {"code": code,
                "kline": kline_json,
                "factors": factors_json,
                "funds": funds,
                "disclaimer": "本内容仅为数据分析学习，不构成投资建议"}
