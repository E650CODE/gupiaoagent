"""
数据采集 Agent - 纯数据逻辑, 不调用 LLM.
依赖 akshare + mootdx, 输出标准化 DataFrame.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.agents.base import BaseAgent
from app.core.exceptions import DataSourceError
from app.core.logger import logger
from app.services import sqlite_store
from app.services.redis_cache import cache, cache_to_df, df_to_cache
from app.utils.data_filter import filter_out_st, filter_tradeable

_DATASOURCE_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)


class DataAgent(BaseAgent):
    name = "data"

    async def _handle(self, payload: dict) -> Any:
        action = payload.get("action", "")
        if action == "stocks":
            return await self.get_all_stocks(refresh=payload.get("refresh", False))
        if action == "kline":
            return await self.get_kline(
                payload["code"], payload.get("start"), payload.get("end"),
                payload.get("adjust", "qfq"),
            )
        if action == "money_flow":
            return await self.get_money_flow(payload["code"])
        if action == "minutes":
            return await self.get_minutes(payload["code"])
        if action == "fundamental":
            return await self.get_fundamental(payload["code"])
        raise DataSourceError(f"unknown action: {action}")

    async def get_all_stocks(self, refresh: bool = False) -> pd.DataFrame:
        """全 A 股代码 + 名称 + 行业, 缓存 1 天."""
        ck = "data:stocks:list"
        if not refresh:
            hit = cache.get(ck)
            if hit:
                df = cache_to_df(hit)
                if df is not None and not df.empty:
                    return df
        df = await asyncio.to_thread(self._fetch_all_stocks)
        df = filter_out_st(df, name_col="name")
        sqlite_store.insert_stock_basic(df)
        cache.set(ck, df_to_cache(df), ttl=86400)
        return df

    @_DATASOURCE_RETRY
    def _fetch_all_stocks(self) -> pd.DataFrame:
        # 主接口: 东方财富全市场实时行情
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                df = df.rename(columns={"代码": "code", "名称": "name"})
                out = df[["code", "name"]].copy()
                out["industry"] = ""
                out["market"] = out["code"].apply(self._guess_market)
                out["list_date"] = ""
                return out
        except Exception as e:
            logger.warning(f"stock_zh_a_spot_em fail, fallback to stock_info_a_code_name: {e}")
        # 备选: 简单接口只返代码+名称
        df = ak.stock_info_a_code_name()
        if df is None or df.empty:
            raise DataSourceError("akshare stocks empty (both endpoints failed)")
        out = df[["code", "name"]].copy()
        out["industry"] = ""
        out["market"] = out["code"].apply(self._guess_market)
        out["list_date"] = ""
        return out

    @staticmethod
    def _guess_market(code: str) -> str:
        if code.startswith(("60", "68")):
            return "SH"
        if code.startswith(("00", "30")):
            return "SZ"
        if code.startswith(("8", "4")):
            return "BJ"
        return ""

    async def get_kline(self, code: str, start=None, end=None, adjust: str = "qfq") -> pd.DataFrame:
        """个股日 K, 默认近 250 个交易日. adjust: qfq/hfq/empty."""
        end = end or datetime.now().strftime("%Y%m%d")
        start = start or (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
        start_n = start.replace("-", "")
        end_n = end.replace("-", "")
        ck = f"data:kline:{code}:{adjust}:{start_n}:{end_n}"
        hit = cache.get(ck)
        if hit:
            df = cache_to_df(hit)
            if df is not None and not df.empty:
                return df
        df = await asyncio.to_thread(self._fetch_kline, code, start_n, end_n, adjust)
        df = filter_tradeable(df)
        if not df.empty:
            df["code"] = code
            sqlite_store.insert_kline(df, adjust)
            cache.set(ck, df_to_cache(df), ttl=43200)
        return df

    @_DATASOURCE_RETRY
    def _fetch_kline(self, code: str, start: str, end: str, adjust: str) -> pd.DataFrame:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust=adjust)
        if df is None or df.empty:
            return pd.DataFrame()
        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low",
            "成交量": "volume", "成交额": "amount",
            "换手率": "turnover", "涨跌幅": "pct_chg",
        }
        df = df.rename(columns=col_map)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        keep = [c for c in ["date","open","high","low","close","volume","amount","turnover","pct_chg"] if c in df.columns]
        return df[keep].reset_index(drop=True)

    async def get_money_flow(self, code: str) -> pd.DataFrame:
        ck = f"data:moneyflow:{code}"
        hit = cache.get(ck)
        if hit:
            df = cache_to_df(hit)
            if df is not None and not df.empty:
                return df
        df = await asyncio.to_thread(self._fetch_money_flow, code)
        if not df.empty:
            cache.set(ck, df_to_cache(df), ttl=3600)
        return df

    @_DATASOURCE_RETRY
    def _fetch_money_flow(self, code: str) -> pd.DataFrame:
        market = "sh" if code.startswith(("60","68")) else "sz"
        try:
            df = ak.stock_individual_fund_flow(stock=code, market=market)
        except Exception as e:
            logger.warning(f"money_flow {code} fail: {e}")
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        col_map = {
            "日期": "date",
            "主力净流入-净额": "main_net_inflow",
            "主力净流入-净占比": "main_net_inflow_ratio",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df.tail(30).reset_index(drop=True)

    async def get_minutes(self, code: str) -> pd.DataFrame:
        ck = f"data:minutes:{code}"
        hit = cache.get(ck)
        if hit:
            df = cache_to_df(hit)
            if df is not None and not df.empty:
                return df
        df = await asyncio.to_thread(self._fetch_minutes, code)
        if not df.empty:
            cache.set(ck, df_to_cache(df), ttl=3600)
        return df

    @_DATASOURCE_RETRY
    def _fetch_minutes(self, code: str) -> pd.DataFrame:
        try:
            sym = ("sh"+code) if code.startswith(("60","68")) else ("sz"+code)
            df = ak.stock_zh_a_minute(symbol=sym, period="1")
        except Exception as e:
            logger.warning(f"minutes {code} fail: {e}")
            return pd.DataFrame()
        return df if df is not None else pd.DataFrame()

    async def get_fundamental(self, code: str) -> dict:
        ck = f"data:fund:{code}"
        hit = cache.get(ck)
        if hit and isinstance(hit, dict):
            return hit
        info = await asyncio.to_thread(self._fetch_fundamental, code)
        if info:
            cache.set(ck, info, ttl=86400)
        return info

    @_DATASOURCE_RETRY
    def _fetch_fundamental(self, code: str) -> dict:
        try:
            df = ak.stock_individual_info_em(symbol=code)
        except Exception as e:
            logger.warning(f"fundamental {code} fail: {e}")
            return {}
        if df is None or df.empty:
            return {}
        out = {}
        for _, row in df.iterrows():
            k = str(row.get("item", "")).strip()
            v = row.get("value", "")
            if k:
                out[k] = v
        return out
