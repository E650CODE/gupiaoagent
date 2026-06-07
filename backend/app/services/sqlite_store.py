"""
SQLite 持久化存储。
表结构：stock_basic / kline_daily / factor_snapshot / backtest_record。
自动建表；提供批量 upsert 和查询方法。
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from app.core.config import settings
from app.core.logger import logger

# 线程局部连接
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        path = Path(settings.SQLITE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(path), check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
    return _local.conn


@contextmanager
def _cursor() -> Iterator[sqlite3.Cursor]:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def init_db() -> None:
    """建表（幂等）。"""
    with _cursor() as cur:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS stock_basic (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT DEFAULT '',
                market TEXT DEFAULT '',
                list_date TEXT DEFAULT '',
                update_time TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS kline_daily (
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                adjust_flag TEXT DEFAULT 'qfq',
                PRIMARY KEY (code, date, adjust_flag)
            );

            CREATE TABLE IF NOT EXISTS factor_snapshot (
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                factors TEXT DEFAULT '{}',
                update_time TEXT DEFAULT (datetime('now','localtime')),
                PRIMARY KEY (code, date)
            );

            CREATE TABLE IF NOT EXISTS backtest_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                params TEXT DEFAULT '{}',
                result TEXT DEFAULT '{}',
                nav_curve TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_kline_code ON kline_daily(code);
            CREATE INDEX IF NOT EXISTS idx_kline_date ON kline_daily(date);
            CREATE INDEX IF NOT EXISTS idx_factor_code ON factor_snapshot(code);
        """)
    logger.info("SQLite 表已初始化")


def insert_stock_basic(df: pd.DataFrame) -> int:
    """批量 upsert 股票基础信息。返回行数。"""
    if df.empty:
        return 0
    with _cursor() as cur:
        for _, row in df.iterrows():
            cur.execute(
                """INSERT OR REPLACE INTO stock_basic
                   (code, name, industry, market, list_date) VALUES (?,?,?,?,?)""",
                (str(row.get("code","")), str(row.get("name","")),
                 str(row.get("industry","")), str(row.get("market","")),
                 str(row.get("list_date",""))),
            )
        return cur.rowcount


def insert_kline(df: pd.DataFrame, adjust_flag: str = "qfq") -> int:
    """批量 upsert K 线。返回行数。"""
    if df.empty:
        return 0
    with _cursor() as cur:
        for _, row in df.iterrows():
            cur.execute(
                """INSERT OR REPLACE INTO kline_daily
                   (code, date, open, high, low, close, volume, amount, adjust_flag)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (str(row.get("code","")), str(row.get("date","")),
                 float(row.get("open",0)), float(row.get("high",0)),
                 float(row.get("low",0)), float(row.get("close",0)),
                 float(row.get("volume",0)), float(row.get("amount",0)),
                 adjust_flag),
            )
        return cur.rowcount


def query_kline(code: str, start: str = "", end: str = "", adjust: str = "qfq") -> pd.DataFrame:
    """查询 K 线数据。"""
    sql = """SELECT * FROM kline_daily
             WHERE code=? AND adjust_flag=?"""
    params = [code, adjust]
    if start:
        sql += " AND date>=?"
        params.append(start)
    if end:
        sql += " AND date<=?"
        params.append(end)
    sql += " ORDER BY date ASC"
    return pd.read_sql(sql, _get_conn(), params=params)


def insert_factor_snapshot(code: str, date: str, factors_json: str) -> None:
    with _cursor() as cur:
        cur.execute(
            """INSERT OR REPLACE INTO factor_snapshot (code, date, factors)
               VALUES (?,?,?)""",
            (code, date, factors_json),
        )


def save_backtest_record(strategy: str, start: str, end: str, params: dict, result: dict, nav: list) -> int:
    """保存回测记录，返回 id。"""
    import json
    with _cursor() as cur:
        cur.execute(
            """INSERT INTO backtest_record (strategy, start_date, end_date, params, result, nav_curve)
               VALUES (?,?,?,?,?,?)""",
            (strategy, start, end, json.dumps(params, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False), json.dumps(nav, ensure_ascii=False)),
        )
        return cur.lastrowid


def get_stock_list() -> pd.DataFrame:
    """读取全市场股票列表。"""
    return pd.read_sql("SELECT * FROM stock_basic ORDER BY code", _get_conn())
