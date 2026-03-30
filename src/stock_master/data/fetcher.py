"""AkShare 数据采集模块."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd


def fetch_stock_info(code: str) -> dict:
    """获取股票基本信息."""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        info = {}
        for _, row in df.iterrows():
            info[row["item"]] = row["value"]
        return info
    except Exception as e:
        return {"error": str(e)}


def fetch_daily_kline(
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取日 K 线数据（前复权）."""
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    df = ak.stock_zh_a_hist(
        symbol=code,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
    return df


def fetch_financial_summary(code: str) -> pd.DataFrame:
    """获取最近的财务摘要数据."""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
        return df.head(5)
    except Exception:
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code)
            return df.head(5)
        except Exception:
            return pd.DataFrame()


def fetch_valuation(code: str) -> dict:
    """获取当前估值指标."""
    try:
        df = ak.stock_a_indicator_lg(symbol=code)
        if df.empty:
            return {}
        latest = df.iloc[-1]
        return {
            "pe": latest.get("pe", None),
            "pe_ttm": latest.get("pe_ttm", None),
            "pb": latest.get("pb", None),
            "ps": latest.get("ps", None),
            "ps_ttm": latest.get("ps_ttm", None),
            "dv_ratio": latest.get("dv_ratio", None),
            "total_mv": latest.get("total_mv", None),
        }
    except Exception:
        return {}


def fetch_news(code: str, limit: int = 10) -> list[dict]:
    """获取个股近期新闻."""
    try:
        df = ak.stock_news_em(symbol=code)
        rows = df.head(limit)
        results = []
        for _, row in rows.iterrows():
            results.append({
                "title": row.get("新闻标题", ""),
                "content": row.get("新闻内容", ""),
                "time": str(row.get("发布时间", "")),
                "source": row.get("文章来源", ""),
                "url": row.get("新闻链接", ""),
            })
        return results
    except Exception:
        return []
