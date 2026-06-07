"""
选股策略预置配置。
每个策略定义: 名称、说明、筛选函数逻辑、参数默认值、需计算的因子。
函数接收一行因子数据 (dict)，返回 True/False 表示是否通过。
"""

from typing import Callable

# 策略注册表: {"strategy_key": {"name": ..., "desc": ..., "check": func}}
# func(row: dict, params: dict) -> bool


def _ma_bull(row: dict, params: dict) -> bool:
    """均线多头: MA5 > MA10 > MA20 > MA60 (且当前价在 MA5 上)。"""
    for p in [5, 10, 20, 60]:
        key = f"ma{p}"
        val = row.get(key)
        if val is None or val <= 0:
            return False
    return (
        row["ma5"] > row["ma10"] > row["ma20"] > row["ma60"]
        and row["close"] >= row["ma5"]
    )


def _macd_golden(row: dict, params: dict) -> bool:
    """MACD 零轴上方金叉: dif > dea > 0 且前一日 dif <= dea。"""
    dif = row.get("macd_dif", 0)
    dea = row.get("macd_dea", 0)
    hist = row.get("macd_hist", 0)
    if dif is None or dea is None or hist is None:
        return False
    return dif > dea and dif > 0


def _volume_surge(row: dict, params: dict) -> bool:
    """放量上涨: 量比 > 阈值 且 涨幅 > 0。"""
    ratio = row.get("vol_ratio", 0)
    pct = row.get("pct_chg", 0)
    threshold = params.get("vol_ratio_threshold", 2.0)
    return ratio is not None and ratio > threshold and (pct or 0) > 0


def _money_inflow(row: dict, params: dict) -> bool:
    """主力近 N 日净流入 (需 money_flow 数据, 默认用 main_net_inflow 列)。"""
    inflow = row.get("main_net_inflow", 0)
    return inflow is not None and inflow > 0


def _low_valuation(row: dict, params: dict) -> bool:
    """低估值: PE > 0 且 PE < 行业中位数 (行业中位数需外部传入)。"""
    pe = row.get("pe", None)
    if pe is None or pe <= 0:
        return False
    median_pe = params.get("industry_pe_median")
    if median_pe and pe >= median_pe:
        return False
    return True


# ===== 注册表 =====
STRATEGY_REGISTRY: dict[str, dict] = {
    "ma_bull": {
        "name": "均线多头",
        "desc": "MA5 > MA10 > MA20 > MA60，当前价在 MA5 上方",
        "check": _ma_bull,
        "params": {},
    },
    "macd_golden": {
        "name": "MACD 零轴上方金叉",
        "desc": "DIF > DEA > 0 (零轴上方)，多头启动信号",
        "check": _macd_golden,
        "params": {},
    },
    "volume_surge": {
        "name": "放量上涨",
        "desc": "量比 > 2.0 且收阳",
        "check": _volume_surge,
        "params": {"vol_ratio_threshold": 2.0},
    },
    "money_inflow": {
        "name": "主力资金净流入",
        "desc": "近 5 日主力资金净额 > 0",
        "check": _money_inflow,
        "params": {},
    },
    "low_valuation": {
        "name": "低估值",
        "desc": "PE > 0 且低于行业中位数",
        "check": _low_valuation,
        "params": {},
    },
}