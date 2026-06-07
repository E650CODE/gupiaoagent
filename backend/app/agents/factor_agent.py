"""
因子指标 Agent - 基于 TA-Lib + 自定义逻辑.
纯数值计算, 无 LLM. 输入 K 线 DataFrame, 输出追加完整因子列的标准数据集.

支持因子:
- MA 均线 (5/10/20/60)
- MACD (12,26,9)
- KDJ (9,3,3)
- BOLL 布林带 (20,2)
- RSI (6/12/24)
- 量比 (5)
- 换手率 (依赖外部基本面)
- 乖离率 (6)
"""

from typing import Any

import numpy as np
import pandas as pd
import talib

from app.agents.base import BaseAgent
from app.core.exceptions import InvalidParamError


# 默认参数, 可被请求覆盖
DEFAULT_PARAMS = {
    "ma_periods": [5, 10, 20, 60],
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "kdj_n": 9,
    "kdj_m1": 3,
    "kdj_m2": 3,
    "boll_n": 20,
    "boll_k": 2,
    "rsi_periods": [6, 12, 24],
    "volume_ratio_n": 5,
    "bias_n": 6,
}


def _winsorize(s: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """对极值做 1%/99% 截尾."""
    if s.empty:
        return s
    lo, hi = s.quantile(lower), s.quantile(upper)
    return s.clip(lo, hi)


# ============== 单因子函数 ==============

def calc_ma(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """计算多周期 MA."""
    close = df["close"].astype(float).values
    for p in periods:
        df[f"ma{p}"] = talib.SMA(close, timeperiod=p)
    return df


def calc_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    """MACD: dif/dea/hist."""
    close = df["close"].astype(float).values
    dif, dea, hist = talib.MACD(close, fastperiod=fast, slowperiod=slow, signalperiod=signal)
    df["macd_dif"] = dif
    df["macd_dea"] = dea
    df["macd_hist"] = hist * 2  # 通达信口径
    return df


def calc_kdj(df: pd.DataFrame, n: int, m1: int, m2: int) -> pd.DataFrame:
    """KDJ. 国内常用通达信算法 (与 talib STOCH 略不同)."""
    low = df["low"].astype(float)
    high = df["high"].astype(float)
    close = df["close"].astype(float)
    llv = low.rolling(n).min()
    hhv = high.rolling(n).max()
    rsv = (close - llv) / (hhv - llv).replace(0, np.nan) * 100
    rsv = rsv.fillna(50)
    k = rsv.ewm(alpha=1/m1, adjust=False).mean()
    d = k.ewm(alpha=1/m2, adjust=False).mean()
    j = 3 * k - 2 * d
    df["kdj_k"] = k
    df["kdj_d"] = d
    df["kdj_j"] = j
    return df


def calc_boll(df: pd.DataFrame, n: int, k: int) -> pd.DataFrame:
    """布林带 upper/middle/lower."""
    close = df["close"].astype(float).values
    upper, middle, lower = talib.BBANDS(close, timeperiod=n, nbdevup=k, nbdevdn=k, matype=0)
    df["boll_upper"] = upper
    df["boll_mid"] = middle
    df["boll_lower"] = lower
    return df


def calc_rsi(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """多周期 RSI."""
    close = df["close"].astype(float).values
    for p in periods:
        df[f"rsi{p}"] = talib.RSI(close, timeperiod=p)
    return df


def calc_volume_ratio(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """量比 = 当日成交量 / 前 N 日均量."""
    vol = df["volume"].astype(float)
    avg = vol.rolling(n).mean().shift(1)  # shift(1) 禁用未来函数
    df["vol_ratio"] = vol / avg.replace(0, np.nan)
    return df


def calc_bias(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """乖离率 = (close - MA_n) / MA_n * 100."""
    close = df["close"].astype(float)
    ma = close.rolling(n).mean()
    df[f"bias{n}"] = (close - ma) / ma.replace(0, np.nan) * 100
    return df


# ============== Agent ==============

class FactorAgent(BaseAgent):
    name = "factor"

    async def _handle(self, payload: dict) -> Any:
        df = payload.get("df")
        if df is None or not isinstance(df, pd.DataFrame):
            raise InvalidParamError("factor agent 需要 df: pd.DataFrame 入参")
        params = {**DEFAULT_PARAMS, **(payload.get("params") or {})}
        return self.calc_all(df, params)

    def calc_all(self, df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
        """对输入的 K 线 DataFrame 计算全部因子."""
        if df.empty:
            return df
        p = {**DEFAULT_PARAMS, **(params or {})}
        df = df.copy()

        # 极值平滑 (仅对涨跌幅/换手率等指标列)
        if "pct_chg" in df.columns:
            df["pct_chg"] = _winsorize(df["pct_chg"].astype(float))

        df = calc_ma(df, p["ma_periods"])
        df = calc_macd(df, p["macd_fast"], p["macd_slow"], p["macd_signal"])
        df = calc_kdj(df, p["kdj_n"], p["kdj_m1"], p["kdj_m2"])
        df = calc_boll(df, p["boll_n"], p["boll_k"])
        df = calc_rsi(df, p["rsi_periods"])
        df = calc_volume_ratio(df, p["volume_ratio_n"])
        df = calc_bias(df, p["bias_n"])

        # 因子列空值前向填充, 避免后续策略报错
        factor_cols = [c for c in df.columns if c not in ("date","open","high","low","close","volume","amount","code")]
        df[factor_cols] = df[factor_cols].ffill()
        return df
