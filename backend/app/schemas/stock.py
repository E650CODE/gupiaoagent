"""选股 / 预测 / 详情 接口 Schema。"""

from pydantic import BaseModel, Field


class SelectRequest(BaseModel):
    strategies: list[str] = Field(..., description="策略 key 列表，AND 组合")
    universe: list[str] | None = Field(None, description="限定股票池，不传则用默认池")
    params: dict | None = Field(None, description="策略参数覆盖")
    top_n: int = Field(20, ge=1, le=100, description="结果上限")
    enable_ai: bool = Field(True, description="是否启用 LLM 解读")
    enable_risk: bool = Field(True, description="是否对结果做风控过滤")


class PredictRequest(BaseModel):
    code: str = Field(..., description="6 位股票代码")
    horizon_days: int = Field(5, ge=3, le=10, description="预测周期 3-10 天")