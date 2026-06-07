"""LLM 路由的请求/响应 Schema。"""

from pydantic import BaseModel, Field


class AgentConfigUpdate(BaseModel):
    """更新单个 Agent 配置，所有字段可选（部分更新）。"""
    provider: str | None = Field(None, description="volcengine / deepseek / openai_compatible")
    base_url: str | None = None
    api_key: str | None = Field(None, description="api_key；含 **** 的掩码值会被忽略")
    model: str | None = None
    timeout: int | None = Field(None, ge=5, le=600)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=16, le=32768)


class UpdateLLMConfigReq(BaseModel):
    agent: str = Field(..., description="selector / predictor / risk / backtest")
    config: AgentConfigUpdate


class FetchModelsReq(BaseModel):
    provider: str = Field("openai_compatible")
    base_url: str
    api_key: str = Field(..., description="api_key 明文；或掩码值则从配置读")


class TestLLMReq(BaseModel):
    provider: str = "openai_compatible"
    base_url: str
    api_key: str
    model: str
