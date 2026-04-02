"""SQLite 本地缓存层."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_DB_PATH = Path("storage/stock_master.db")


class DataCache:
    """基于 SQLite 的数据缓存."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
        return self._conn

    def _init_db(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS kline_cache (
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (code, date)
            );
            CREATE TABLE IF NOT EXISTS info_cache (
                code TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS valuation_cache (
                code TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dataset_cache (
                code TEXT NOT NULL,
                dataset_key TEXT NOT NULL,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (code, dataset_key)
            );
        """)
        self.conn.commit()

    def get_kline(self, code: str, max_age_hours: int = 12) -> Optional[pd.DataFrame]:
        """从缓存读取 K 线数据，超时则返回 None."""
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        row = self.conn.execute(
            "SELECT data FROM kline_cache WHERE code = ? AND fetched_at > ?",
            (code, cutoff),
        ).fetchone()
        if row is None:
            return None
        return pd.read_json(StringIO(row[0]), orient="records")

    def set_kline(self, code: str, df: pd.DataFrame) -> None:
        now = datetime.now().isoformat()
        data = df.to_json(orient="records", force_ascii=False)
        self.conn.execute(
            "INSERT OR REPLACE INTO kline_cache (code, date, data, fetched_at) VALUES (?, ?, ?, ?)",
            (code, now[:10], data, now),
        )
        self.conn.commit()

    def get_info(self, code: str, max_age_hours: int = 24) -> Optional[dict]:
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        row = self.conn.execute(
            "SELECT data FROM info_cache WHERE code = ? AND fetched_at > ?",
            (code, cutoff),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def set_info(self, code: str, info: dict) -> None:
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO info_cache (code, data, fetched_at) VALUES (?, ?, ?)",
            (code, json.dumps(info, ensure_ascii=False), now),
        )
        self.conn.commit()

    def get_valuation(self, code: str, max_age_hours: int = 12) -> Optional[dict]:
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        row = self.conn.execute(
            "SELECT data FROM valuation_cache WHERE code = ? AND fetched_at > ?",
            (code, cutoff),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def set_valuation(self, code: str, val: dict) -> None:
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO valuation_cache (code, data, fetched_at) VALUES (?, ?, ?)",
            (code, json.dumps(val, ensure_ascii=False), now),
        )
        self.conn.commit()

    def get_dataset(
        self,
        code: str,
        dataset_key: str,
        max_age_hours: int = 24,
    ) -> Optional[pd.DataFrame | dict | list | str]:
        """通用数据集缓存读取."""
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        row = self.conn.execute(
            """
            SELECT data FROM dataset_cache
            WHERE code = ? AND dataset_key = ? AND fetched_at > ?
            """,
            (code, dataset_key, cutoff),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        kind = payload.get("kind")
        value = payload.get("value")
        if kind == "dataframe":
            return pd.read_json(StringIO(value), orient="records")
        return value

    def set_dataset(self, code: str, dataset_key: str, value: pd.DataFrame | dict | list | str) -> None:
        """通用数据集缓存写入."""
        now = datetime.now().isoformat()
        if isinstance(value, pd.DataFrame):
            payload = {"kind": "dataframe", "value": value.to_json(orient="records", force_ascii=False)}
        else:
            payload = {"kind": "json", "value": value}
        self.conn.execute(
            """
            INSERT OR REPLACE INTO dataset_cache (code, dataset_key, data, fetched_at)
            VALUES (?, ?, ?, ?)
            """,
            (code, dataset_key, json.dumps(payload, ensure_ascii=False), now),
        )
        self.conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
