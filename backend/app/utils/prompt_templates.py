"""
所有 Agent 的 Prompt 模板集中管理。
便于统一调优、版本化、未来多语言切换。
"""

# ============== 选股 Agent ==============

SELECTOR_SYSTEM = (
    "你是一位资深的 A 股量化分析师，擅长基于多因子模型解读选股结果。\n"
    "任务: 根据用户提供的选股规则、候选股票因子快照，输出结构化的中文分析。\n"
    "必须严格按 JSON 返回，字段:\n"
    "{\n"
    '  "logic": "本次选股逻辑的核心解释 (2-3 句话)",\n'
    '  "common_features": ["共性特征1", "共性特征2", "..."],\n'
    '  "sector_hot": "所属板块热度判断 (1-2 句话)",\n'
    '  "summary": "整体总结 (1 句话)"\n'
    "}\n"
    "本输出仅供学习分析，不构成投资建议。"
)


def selector_user_prompt(rules: list, stocks: list) -> str:
    """构造选股 Agent 的 user prompt。"""
    rules_txt = "\n".join(f"- {r}" for r in rules)
    top = stocks[:15]  # 限制 token
    rows = []
    for s in top:
        rows.append(
            f"{s.get('code','')} {s.get('name','')} | "
            f"close={s.get('close',0):.2f} ma5={s.get('ma5',0):.2f} "
            f"ma20={s.get('ma20',0):.2f} macd_dif={s.get('macd_dif',0):.3f} "
            f"rsi6={s.get('rsi6',0):.1f} vol_ratio={s.get('vol_ratio',0):.2f}"
        )
    stocks_txt = "\n".join(rows)
    return (
        f"【选股规则】\n{rules_txt}\n\n"
        f"【候选股票因子快照 (共 {len(stocks)} 只, 展示前 {len(top)} 只)】\n{stocks_txt}\n\n"
        f"请输出 JSON 格式分析结果。"
    )


# ============== 趋势预测 Agent ==============

PREDICTOR_SYSTEM = (
    "你是一位 A 股短期趋势研判专家，仅做 3-10 个交易日内的方向判断，"
    "禁止给出长期价值分析，禁止给出具体买卖操作建议。\n"
    "必须严格按 JSON 返回:\n"
    "{\n"
    '  "direction": "up|down|range",\n'
    '  "prob": 0.0-1.0,\n'
    '  "price_low": 数字,\n'
    '  "price_high": 数字,\n'
    '  "horizon_days": 3-10 的整数,\n'
    '  "reasoning": "走势逻辑的简要分析 (3-5 句话)",\n'
    '  "risk_warning": "本判断存在的风险点 (1-2 句话)"\n'
    "}\n"
    "本输出仅供学习分析，不构成投资建议。"
)


def predictor_user_prompt(code: str, name: str, snapshot: dict, recent_pct: list) -> str:
    """构造趋势预测的 user prompt。snapshot 为最新一行的因子；recent_pct 为近20日涨跌幅列表。"""
    pct_txt = ", ".join(f"{p:+.2f}%" for p in recent_pct[-20:])
    return (
        f"【个股】 {code} {name}\n\n"
        f"【最新一日因子快照】\n"
        f"- close={snapshot.get('close',0):.2f}\n"
        f"- MA5/10/20/60 = "
        f"{snapshot.get('ma5',0):.2f} / {snapshot.get('ma10',0):.2f} / "
        f"{snapshot.get('ma20',0):.2f} / {snapshot.get('ma60',0):.2f}\n"
        f"- MACD dif/dea/hist = "
        f"{snapshot.get('macd_dif',0):.3f} / {snapshot.get('macd_dea',0):.3f} / {snapshot.get('macd_hist',0):.3f}\n"
        f"- KDJ k/d/j = "
        f"{snapshot.get('kdj_k',0):.1f} / {snapshot.get('kdj_d',0):.1f} / {snapshot.get('kdj_j',0):.1f}\n"
        f"- BOLL upper/mid/lower = "
        f"{snapshot.get('boll_upper',0):.2f} / {snapshot.get('boll_mid',0):.2f} / {snapshot.get('boll_lower',0):.2f}\n"
        f"- RSI6/12/24 = "
        f"{snapshot.get('rsi6',0):.1f} / {snapshot.get('rsi12',0):.1f} / {snapshot.get('rsi24',0):.1f}\n"
        f"- 量比 = {snapshot.get('vol_ratio',0):.2f}, BIAS6 = {snapshot.get('bias6',0):.2f}\n\n"
        f"【近 20 个交易日涨跌幅序列】\n{pct_txt}\n\n"
        f"请预测未来 3-10 个交易日的趋势，返回 JSON。"
    )


# ============== 风控 Agent ==============

RISK_SYSTEM = (
    "你是一位风险控制专家。任务: 基于个股近期数据与本地评级结果，输出风险解读。\n"
    "必须严格按 JSON 返回:\n"
    "{\n"
    '  "risk_points": ["风险点1", "风险点2", "..."],\n'
    '  "stop_profit": 数字 (止盈参考价位),\n'
    '  "stop_loss": 数字 (止损参考价位),\n'
    '  "advice": "持仓风险提示 (2-3 句话)"\n'
    "}\n"
    "止盈止损仅为基于波动率的参考区间，不构成投资建议。"
)


def risk_user_prompt(code: str, name: str, snapshot: dict, local_level: str, recent_pct: list) -> str:
    pct_txt = ", ".join(f"{p:+.2f}%" for p in recent_pct[-10:])
    return (
        f"【个股】 {code} {name}\n"
        f"【本地评级】 {local_level} 风险\n"
        f"【近10日涨跌幅】 {pct_txt}\n"
        f"【最新收盘】 {snapshot.get('close',0):.2f}\n"
        f"【BOLL 区间】 {snapshot.get('boll_lower',0):.2f} ~ {snapshot.get('boll_upper',0):.2f}\n"
        f"【RSI6】 {snapshot.get('rsi6',0):.1f}\n\n"
        f"请输出 JSON 格式的风险分析。"
    )


# ============== 回测 Agent ==============

BACKTEST_SYSTEM = (
    "你是一位策略回测分析专家。任务: 基于策略回测的核心指标，输出结构化总结。\n"
    "必须严格按 JSON 返回:\n"
    "{\n"
    '  "summary": "回测结果总体表现的 2-3 句总结",\n'
    '  "pros": ["策略优点1", "..."],\n'
    '  "cons": ["策略缺点1", "..."],\n'
    '  "optimize": ["参数优化方向1", "..."]\n'
    "}\n"
    "仅为学习分析，不构成投资建议。"
)


def backtest_user_prompt(strategy: str, params: dict, metrics: dict, period: str) -> str:
    return (
        f"【策略】 {strategy}\n"
        f"【参数】 {params}\n"
        f"【回测区间】 {period}\n"
        f"【核心指标】\n"
        f"- 累计收益率: {metrics.get('total_return', 0):.2%}\n"
        f"- 年化收益率: {metrics.get('annual_return', 0):.2%}\n"
        f"- 胜率: {metrics.get('win_rate', 0):.2%}\n"
        f"- 最大回撤: {metrics.get('max_drawdown', 0):.2%}\n"
        f"- 夏普比率: {metrics.get('sharpe', 0):.2f}\n"
        f"- 交易次数: {metrics.get('trade_count', 0)}\n"
        f"- 平均持仓收益: {metrics.get('avg_trade_return', 0):.2%}\n\n"
        f"请输出 JSON 格式的策略评估。"
    )
