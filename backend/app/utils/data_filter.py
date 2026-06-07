"""
A股合规过滤工具：剔除 ST、停牌、一字涨跌停。
所有筛选逻辑必须经过本模块统一处理，避免重复实现。
"""

import pandas as pd


def is_st(name: str) -> bool:
    """是否 ST 股票（含 *ST / SST / S*ST）。"""
    if not isinstance(name, str):
        return False
    n = name.upper().replace(" ", "")
    return ("ST" in n) or n.startswith("*ST") or n.startswith("S*ST")


def filter_out_st(df_stocks: pd.DataFrame, name_col: str = "name") -> pd.DataFrame:
    """剔除 ST 股票列表。"""
    if df_stocks.empty or name_col not in df_stocks.columns:
        return df_stocks
    mask = ~df_stocks[name_col].apply(is_st)
    return df_stocks[mask].reset_index(drop=True)


def is_suspended(row: pd.Series) -> bool:
    """当日是否停牌：成交量=0 或 成交额=0。"""
    vol = row.get("volume", 0) or 0
    amt = row.get("amount", 0) or 0
    return float(vol) == 0 and float(amt) == 0


def is_limit_one_word(row: pd.Series, prev_close: float | None = None) -> bool:
    """
    是否一字涨跌停：开=高=低=收 且 涨跌幅触板（±10% 主板 / ±20% 创业板科创板）。
    若无 prev_close，按 9.8% 阈值粗判。
    """
    o, h, l, c = (row.get("open", 0), row.get("high", 0),
                  row.get("low", 0), row.get("close", 0))
    if not (o == h == l == c) or c == 0:
        return False
    if prev_close and prev_close > 0:
        pct = (c - prev_close) / prev_close
        return abs(pct) >= 0.098
    return True  # 严格 4 价合一，谨慎按一字板处理


def filter_tradeable(df_kline: pd.DataFrame) -> pd.DataFrame:
    """
    输入个股 K 线 DataFrame（含 open/high/low/close/volume/amount），
    剔除停牌行与一字涨跌停行。
    """
    if df_kline.empty:
        return df_kline
    df = df_kline.copy()
    # 停牌
    df = df[~df.apply(is_suspended, axis=1)]
    # 一字板：取前一日收盘做判断
    if "close" in df.columns:
        df["_prev_close"] = df["close"].shift(1)
        mask = df.apply(
            lambda r: not is_limit_one_word(r, r.get("_prev_close")), axis=1
        )
        df = df[mask].drop(columns=["_prev_close"])
    return df.reset_index(drop=True)
