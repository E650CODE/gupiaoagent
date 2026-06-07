"""
自研轻量回测引擎 (默认引擎)。
工作流程:
1. 对回测区间内的每个交易日 T:
   - 拉取股票池所有股票截至 T 日的 K 线 + 因子
   - 应用策略筛选, 得到当日候选
   - 若有可用现金且未持有, 等权买入 (限定单次最多 N 只)
2. 持有 hold_days 后卖出
3. 每日结算净值 = 现金 + 持仓市值
4. 输出累计收益、年化、胜率、最大回撤、夏普
"""

import math
from typing import Callable

import numpy as np
import pandas as pd

from app.backtest.engine_base import BacktestEngine, BacktestResult, register_engine
from app.core.logger import logger
from app.strategies.presets import STRATEGY_REGISTRY


@register_engine("simple")
class SimpleEngine(BacktestEngine):
    name = "simple"

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
        params = params or {}
        initial_cash = float(params.get("initial_cash", 100_000.0))
        hold_days = int(params.get("hold_days", 5))
        max_positions = int(params.get("max_positions", 5))
        position_size = initial_cash / max_positions

        if strategy_key not in STRATEGY_REGISTRY:
            raise ValueError(f"未知策略: {strategy_key}")
        strategy = STRATEGY_REGISTRY[strategy_key]
        check_func = strategy["check"]
        strategy_params = strategy.get("params", {})

        # 限定回测股票池 (无传入则用一个小池子, 避免拉太久)
        universe = universe or self._default_universe()
        logger.info(f"[backtest] strategy={strategy_key} universe={len(universe)} {start}~{end}")

        # 1) 拉所有股票的 K 线 + 算因子, 按日期建立索引
        all_data: dict[str, pd.DataFrame] = {}
        for code in universe:
            try:
                kdf = await kline_provider(code, start, end)
                if kdf.empty or len(kdf) < 60:
                    continue
                fdf = factor_calculator(kdf)
                fdf = fdf.dropna(subset=["ma60"])  # 至少有 60 日数据才参与
                all_data[code] = fdf
            except Exception as e:
                logger.warning(f"[backtest] {code} 数据失败: {e}")
                continue

        if not all_data:
            return BacktestResult(metrics={"error": "无可用数据"})

        # 2) 收集全部交易日
        all_dates = set()
        for df in all_data.values():
            all_dates.update(df["date"].tolist())
        trade_dates = sorted(all_dates)

        # 3) 模拟交易
        cash = initial_cash
        positions: dict[str, dict] = {}  # code -> {entry_price, qty, entry_date, exit_date}
        nav_curve = []
        trades = []
        wins = 0
        losses = 0
        trade_returns = []

        for date in trade_dates:
            # —— 先平仓: 到期持仓全部卖出 ——
            to_close = [code for code, p in positions.items() if p["exit_date"] <= date]
            for code in to_close:
                pos = positions.pop(code)
                df = all_data[code]
                row = df[df["date"] == date]
                if row.empty:
                    # 当日无价 (可能停牌), 用最近一日收盘价兜底
                    row = df[df["date"] <= date].tail(1)
                if row.empty:
                    continue
                sell_price = float(row.iloc[0]["close"])
                pnl = (sell_price - pos["entry_price"]) * pos["qty"]
                cash += sell_price * pos["qty"]
                ret = (sell_price - pos["entry_price"]) / pos["entry_price"]
                trade_returns.append(ret)
                if ret > 0:
                    wins += 1
                else:
                    losses += 1
                trades.append({
                    "date": date, "code": code, "action": "sell",
                    "price": round(sell_price, 2), "qty": pos["qty"],
                    "pnl": round(pnl, 2), "return": round(ret, 4),
                })

            # —— 再开仓: 当日满足策略且未持有 ——
            if len(positions) < max_positions:
                candidates = []
                for code, df in all_data.items():
                    if code in positions:
                        continue
                    row_idx = df.index[df["date"] == date]
                    if len(row_idx) == 0:
                        continue
                    row = df.loc[row_idx[0]].to_dict()
                    if not all(k in row and row[k] is not None for k in ("close","ma5","ma60")):
                        continue
                    try:
                        if check_func(row, strategy_params):
                            candidates.append((code, row))
                    except Exception:
                        continue

                slots_left = max_positions - len(positions)
                for code, row in candidates[:slots_left]:
                    price = float(row["close"])
                    if price <= 0 or cash < position_size:
                        continue
                    qty = int(position_size / price / 100) * 100  # 100 股整数
                    if qty <= 0:
                        continue
                    cost = qty * price
                    if cost > cash:
                        continue
                    cash -= cost
                    # 计算 exit_date: 当前日期之后第 hold_days 个交易日
                    try:
                        cur_idx = trade_dates.index(date)
                        exit_idx = min(cur_idx + hold_days, len(trade_dates) - 1)
                        exit_date = trade_dates[exit_idx]
                    except ValueError:
                        exit_date = date
                    positions[code] = {
                        "entry_price": price, "qty": qty,
                        "entry_date": date, "exit_date": exit_date,
                    }
                    trades.append({
                        "date": date, "code": code, "action": "buy",
                        "price": round(price, 2), "qty": qty,
                        "pnl": 0, "return": 0,
                    })

            # —— 当日净值 ——
            mkt_value = 0.0
            for code, pos in positions.items():
                df = all_data[code]
                row = df[df["date"] == date]
                if row.empty:
                    row = df[df["date"] <= date].tail(1)
                cur_price = float(row.iloc[0]["close"]) if not row.empty else pos["entry_price"]
                mkt_value += cur_price * pos["qty"]
            nav = cash + mkt_value
            nav_curve.append({
                "date": date,
                "nav": round(nav, 2),
                "cash": round(cash, 2),
                "holdings": len(positions),
            })

        # 4) 指标计算
        navs = np.array([n["nav"] for n in nav_curve])
        if len(navs) < 2:
            return BacktestResult(metrics={"error": "净值数据不足"}, trades=trades, nav_curve=nav_curve)
        total_return = navs[-1] / navs[0] - 1
        days = len(navs)
        annual = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        # 回撤
        peak = np.maximum.accumulate(navs)
        drawdown = (navs - peak) / peak
        max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0
        # 夏普
        daily_ret = np.diff(navs) / navs[:-1]
        sharpe = float(np.sqrt(252) * daily_ret.mean() / (daily_ret.std() + 1e-9)) if len(daily_ret) > 1 else 0
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        avg_ret = float(np.mean(trade_returns)) if trade_returns else 0

        metrics = {
            "total_return": float(total_return),
            "annual_return": float(annual),
            "win_rate": float(win_rate),
            "max_drawdown": float(max_dd),
            "sharpe": float(sharpe),
            "trade_count": wins + losses,
            "avg_trade_return": avg_ret,
            "initial_nav": float(navs[0]),
            "final_nav": float(navs[-1]),
        }
        return BacktestResult(metrics=metrics, nav_curve=nav_curve, trades=trades)

    @staticmethod
    def _default_universe() -> list[str]:
        """默认股票池 (沪深 300 头部样本, 避免拉全市场太慢)。"""
        return [
            "600519", "601318", "600036", "000858", "000333",
            "600276", "601166", "002594", "000651", "600030",
            "601012", "002415", "300750", "600887", "000725",
            "601398", "601628", "601988", "601857", "600028",
        ]