"""FactorAgent 单元测试 - 用固定 K 线断言指标稳定性。"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.factor_agent import FactorAgent  # noqa: E402


def _make_kline(n: int = 100) -> pd.DataFrame:
    """构造确定性 K 线: close = 10 + 0.1*i + 0.5*sin(i/5)"""
    idx = np.arange(n)
    close = 10 + 0.1 * idx + 0.5 * np.sin(idx / 5)
    high = close + 0.3
    low = close - 0.3
    op = close - 0.1
    vol = (1000 + 50 * np.sin(idx / 3)).astype(float)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
        "open": op, "high": high, "low": low, "close": close,
        "volume": vol, "amount": vol * close, "pct_chg": np.zeros(n),
    })


def test_calc_all_columns_present():
    df = _make_kline()
    out = FactorAgent().calc_all(df)
    # 必须新增的列
    expected = {
        "ma5","ma10","ma20","ma60",
        "macd_dif","macd_dea","macd_hist",
        "kdj_k","kdj_d","kdj_j",
        "boll_upper","boll_mid","boll_lower",
        "rsi6","rsi12","rsi24",
        "vol_ratio","bias6",
    }
    assert expected.issubset(set(out.columns)), f"missing: {expected - set(out.columns)}"


def test_ma_no_future_function():
    """MA 末值应该 = 末尾 N 根 close 的均值,不包含未来数据."""
    df = _make_kline(50)
    out = FactorAgent().calc_all(df, {"ma_periods": [5]})
    expected_last_ma5 = df["close"].iloc[-5:].mean()
    assert abs(out["ma5"].iloc[-1] - expected_last_ma5) < 1e-6


def test_volume_ratio_uses_shifted_mean():
    """量比的分母用 shift(1) 的前 N 日均量,确保不偷看当日."""
    df = _make_kline(20)
    out = FactorAgent().calc_all(df, {"volume_ratio_n": 5})
    # 最后一行的量比应 = vol[-1] / mean(vol[-6:-1])
    expected = df["volume"].iloc[-1] / df["volume"].iloc[-6:-1].mean()
    assert abs(out["vol_ratio"].iloc[-1] - expected) < 1e-6


def test_handles_empty_dataframe():
    out = FactorAgent().calc_all(pd.DataFrame())
    assert out.empty


def test_winsorize_caps_extremes():
    """单元测试 winsorize 是否能截断极值."""
    from app.agents.factor_agent import _winsorize
    s = pd.Series([1,2,3,4,5,6,7,8,9,1000])
    out = _winsorize(s, 0.0, 0.9)
    assert out.max() < 1000  # 100 分位数被压缩
