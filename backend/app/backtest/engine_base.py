"""
回测引擎抽象层。
预留扩展点: 未来可接入 vectorbt / backtrader / 自定义引擎。
新引擎只需继承 BacktestEngine 并在 ENGINE_REGISTRY 注册。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd


@dataclass
class BacktestResult:
    """统一回测结果结构。"""
    metrics: dict = field(default_factory=dict)        # 收益/胜率/回撤/夏普等核心指标
    nav_curve: list = field(default_factory=list)      # 净值曲线 [{date, nav, cash, holdings}]
    trades: list = field(default_factory=list)         # 交易明细 [{date, code, action, price, ...}]
    extra: dict = field(default_factory=dict)          # 引擎私有数据


class BacktestEngine(ABC):
    """
    回测引擎抽象基类。
    参数说明:
      - strategy_key: 策略 key (对应 STRATEGY_REGISTRY)
      - kline_provider: async callable(code, start, end) -> DataFrame, 提供 K 线
      - universe: 可选, 限定回测股票池 (代码列表); 不传则全市场
      - params: 引擎参数 (初始资金/持仓周期/单笔仓位等)
    """

    name: str = "base"

    @abstractmethod
    async def run(
        self,
        strategy_key: str,
        start: str,
        end: str,
        kline_provider: Callable,
        factor_calculator: Callable,
        universe: list[str] | None = None,
        params: dict | None = None,
    ) -> BacktestResult:
        ...


# 引擎注册表: 业务可通过 key 选择引擎, 默认 "simple"
ENGINE_REGISTRY: dict[str, type[BacktestEngine]] = {}


def register_engine(key: str):
    """装饰器: 注册回测引擎。"""
    def deco(cls: type[BacktestEngine]):
        ENGINE_REGISTRY[key] = cls
        return cls
    return deco


def get_engine(key: str = "simple") -> BacktestEngine:
    """工厂方法: 按 key 取引擎实例。"""
    cls = ENGINE_REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"未知回测引擎: {key}; 可选: {list(ENGINE_REGISTRY.keys())}")
    return cls()