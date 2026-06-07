"""
个股相关业务路由:
- POST /api/v1/stock/select   多因子选股
- POST /api/v1/stock/predict  趋势预测
- GET  /api/v1/stock/detail/{code} 个股 K线+因子+资金流
- GET  /api/v1/stock/strategies 内置策略列表
- GET  /api/v1/stock/list 全市场列表
"""

from fastapi import APIRouter, Path

from app.agents.master_agent import MasterAgent
from app.schemas.common import Resp
from app.schemas.stock import PredictRequest, SelectRequest
from app.strategies.presets import STRATEGY_REGISTRY

router = APIRouter(prefix="/stock", tags=["stock"])

_master: MasterAgent | None = None


def get_master() -> MasterAgent:
    """惰性单例：避免每个请求都重建 Agent。"""
    global _master
    if _master is None:
        _master = MasterAgent()
    return _master


@router.post("/select", summary="多因子选股")
async def select_stocks(req: SelectRequest):
    out = await get_master().handle_select(req.model_dump())
    return Resp.ok(out)


@router.post("/predict", summary="单股趋势预测")
async def predict_stock(req: PredictRequest):
    out = await get_master().handle_predict(req.model_dump())
    return Resp.ok(out)


@router.get("/detail/{code}", summary="个股详情 (K线+因子+资金流)")
async def stock_detail(code: str = Path(..., min_length=6, max_length=6)):
    out = await get_master().handle_detail(code)
    return Resp.ok(out)


@router.get("/strategies", summary="内置选股策略列表")
async def list_strategies():
    return Resp.ok(
        [
            {"key": k, "name": v["name"], "desc": v["desc"], "params": v.get("params", {})}
            for k, v in STRATEGY_REGISTRY.items()
        ]
    )


@router.get("/list", summary="全市场股票列表")
async def stock_list():
    master = get_master()
    df = await master.data_agent.get_all_stocks()
    return Resp.ok(df.to_dict(orient="records") if not df.empty else [])