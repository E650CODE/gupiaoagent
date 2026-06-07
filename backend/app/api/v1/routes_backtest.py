"""回测业务路由。"""

from fastapi import APIRouter

from app.agents.master_agent import MasterAgent
from app.schemas.backtest import BacktestRequest
from app.schemas.common import Resp

router = APIRouter(prefix="/backtest", tags=["backtest"])

_master: MasterAgent | None = None


def get_master() -> MasterAgent:
    global _master
    if _master is None:
        _master = MasterAgent()
    return _master


@router.post("/run", summary="回测")
async def run_backtest(req: BacktestRequest):
    out = await get_master().handle_backtest(req.model_dump())
    return Resp.ok(out)