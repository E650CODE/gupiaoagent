"""
LLM 配置与管理路由：
- GET  /api/v1/llm/config           获取所有 Agent 配置（api_key 掩码）
- PUT  /api/v1/llm/config           更新指定 Agent 配置
- POST /api/v1/llm/models           由 base_url+api_key 自动拉取可用模型列表
- POST /api/v1/llm/test             连通性测试
"""

from fastapi import APIRouter

from app.core.exceptions import LLMConfigError, LLMRequestError
from app.schemas.common import Resp
from app.schemas.llm import FetchModelsReq, TestLLMReq, UpdateLLMConfigReq
from app.services import llm_client, llm_config_store, llm_providers

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/config", summary="获取所有 Agent 的 LLM 配置")
async def get_config():
    return Resp.ok(llm_config_store.list_config_masked())


@router.put("/config", summary="更新指定 Agent 的 LLM 配置")
async def put_config(req: UpdateLLMConfigReq):
    updated = llm_config_store.update_agent_config(
        req.agent, req.config.model_dump(exclude_none=True)
    )
    # 出参也掩码 api_key
    return Resp.ok(
        {
            "agent": req.agent,
            "config": {**updated, "api_key": llm_config_store.mask_key(updated.get("api_key", ""))},
        }
    )


@router.post("/models", summary="自动拉取该 Provider/Key 支持的模型列表")
async def fetch_models(req: FetchModelsReq):
    # 若收到掩码值，则用已存配置里的真实 key（按 provider 推断关联 Agent 比较麻烦，前端应传明文）
    if "****" in req.api_key:
        raise LLMRequestError("api_key 为掩码值，请重新输入完整 key 后再获取模型列表")
    try:
        models = llm_providers.list_models(req.provider, req.base_url, req.api_key)
        return Resp.ok({"provider": req.provider, "models": models, "count": len(models)})
    except Exception as e:
        return Resp.fail(3002, f"拉取模型列表失败: {e}")


@router.post("/test", summary="测试 LLM 配置连通性")
async def test_llm(req: TestLLMReq):
    if "****" in req.api_key:
        raise LLMRequestError("api_key 为掩码值，请重新输入完整 key 后再测试")
    result = llm_client.test_connection(req.provider, req.base_url, req.api_key, req.model)
    return Resp.ok(result)


@router.get("/providers", summary="返回内置 provider 预设（base_url 模板）")
async def list_providers():
    return Resp.ok(llm_config_store.PROVIDER_PRESETS)
