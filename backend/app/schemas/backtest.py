"""回测接口 Schema。"""

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy: str = Field(..., description="策略 key (单一策略)")
    start: str = Field(..., description="回测开始日 YYYYMMDD")
    end: str = Field(..., description="回测结束日 YYYYMMDD")
    universe: list[str] | None = Field(None, description="限定股票池")
    params: dict | None = Field(
        None,
        description="引擎参数: initial_cash/hold_days/max_positions",
    )
    engine: str = Field("simple", description="引擎 key (预留扩展)")
    enable_ai: bool = Field(True, description="是否启用 LLM 总结")