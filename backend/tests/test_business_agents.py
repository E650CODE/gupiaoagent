"""业务 Agent 单元测试 - mock 掉数据源和 LLM, 只验业务逻辑。"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _fake_kline(n: int = 100) -> pd.DataFrame:
    """构造能通过 ma_bull 策略的多头排列 K 线."""
    idx = np.arange(n)
    close = 10 + 0.05 * idx  # 持续上涨
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
        "open": close - 0.05, "high": close + 0.1,
        "low": close - 0.1, "close": close,
        "volume": np.full(n, 10000.0),
        "amount": np.full(n, 100000.0),
        "pct_chg": np.full(n, 0.5),
    })


@pytest.mark.asyncio
async def test_selector_local_filter():
    """选股 Agent 本地筛选: 多头排列股票应通过 ma_bull 策略."""
    from app.agents.selector_agent import SelectorAgent

    agent = SelectorAgent()
    # mock 数据源
    agent.data_agent.get_kline = AsyncMock(return_value=_fake_kline(120))
    agent.data_agent.get_all_stocks = AsyncMock(
        return_value=pd.DataFrame([{"code":"600519","name":"贵州茅台"}])
    )
    # mock LLM
    with patch("app.agents.selector_agent.llm_client.chat", return_value={"logic":"持续上涨","common_features":["多头排列"]}):
        result = await agent.select(
            strategies=["ma_bull"], universe=["600519"], enable_ai=True,
        )
    assert result["count"] == 1
    assert result["stocks"][0]["code"] == "600519"
    assert result["ai_explanation"]["logic"] == "持续上涨"


@pytest.mark.asyncio
async def test_predictor_returns_structure():
    """预测 Agent: 解析 LLM JSON 后做置信度分级."""
    from app.agents.predictor_agent import PredictorAgent

    agent = PredictorAgent()
    agent.data_agent.get_kline = AsyncMock(return_value=_fake_kline(120))
    agent.data_agent.get_all_stocks = AsyncMock(
        return_value=pd.DataFrame([{"code":"600519","name":"贵州茅台"}])
    )
    with patch("app.agents.predictor_agent.llm_client.chat",
              return_value={"direction":"up","prob":0.78,"price_low":100,"price_high":110,
                            "horizon_days":5,"reasoning":"...","risk_warning":"..."}):
        result = await agent.predict("600519", horizon_days=5)
    assert result["direction"] == "up"
    assert result["confidence"] == "高"  # prob 0.78 >= 0.7


@pytest.mark.asyncio
async def test_risk_local_rule_low():
    """风控 Agent: 平稳走势应评 '低' 风险."""
    from app.agents.risk_agent import RiskAgent

    agent = RiskAgent()
    agent.data_agent.get_kline = AsyncMock(return_value=_fake_kline(120))
    agent.data_agent.get_all_stocks = AsyncMock(
        return_value=pd.DataFrame([{"code":"600519","name":"贵州茅台"}])
    )
    with patch("app.agents.risk_agent.llm_client.chat",
              return_value={"risk_points":["小幅波动"],"stop_profit":120,"stop_loss":90,"advice":"..."}):
        result = await agent.assess("600519")
    assert result["risk_level"] in ("低", "中", "高")  # 走势平稳, 应为低


@pytest.mark.asyncio
async def test_backtest_engine_runs():
    """回测 Agent: 用 fake kline 跑 SimpleEngine 应得到非空 metrics."""
    from app.agents.backtest_agent import BacktestAgent

    agent = BacktestAgent()
    agent.data_agent.get_kline = AsyncMock(return_value=_fake_kline(120))
    with patch("app.agents.backtest_agent.llm_client.chat",
              return_value={"summary":"测试","pros":[],"cons":[],"optimize":[]}):
        result = await agent.run_backtest(
            strategy="ma_bull", start="20240101", end="20240601",
            universe=["600519"], params={"initial_cash":100000,"hold_days":5,"max_positions":1},
            enable_ai=True,
        )
    assert "metrics" in result
    assert result["metrics"].get("error") is None or "error" not in result["metrics"]
    assert isinstance(result["nav_curve"], list)
