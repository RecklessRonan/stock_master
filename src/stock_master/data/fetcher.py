"""AkShare 数据采集模块，支持 A 股与港股."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd


@contextmanager
def _bypass_proxy():
    """临时设置 NO_PROXY=* 绕过系统/环境变量代理."""
    env_keys = ("http_proxy", "https_proxy", "all_proxy",
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "no_proxy")
    old = {k: os.environ.get(k) for k in env_keys}
    try:
        for k in env_keys:
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def is_hk_stock(code: str) -> bool:
    """判断股票代码是否为港股（5 位数字）."""
    digits = code.lstrip("0")
    return len(code) == 5 or (len(code) > 0 and len(digits) <= 4 and code.isdigit())


# ---------------------------------------------------------------------------
# 基本信息
# ---------------------------------------------------------------------------

def fetch_stock_info(code: str) -> dict:
    """获取股票基本信息（自动区分 A 股/港股）."""
    if is_hk_stock(code):
        return _fetch_stock_info_hk(code)
    return _fetch_stock_info_a(code)


def _fetch_stock_info_a(code: str) -> dict:
    try:
        with _bypass_proxy():
            df = ak.stock_individual_info_em(symbol=code)
        info = {}
        for _, row in df.iterrows():
            info[row["item"]] = row["value"]
        return info
    except Exception as e:
        return {"error": str(e)}


def _fetch_stock_info_hk(code: str) -> dict:
    try:
        with _bypass_proxy():
            sec = ak.stock_hk_security_profile_em(symbol=code)
        info: dict = {}
        if not sec.empty:
            row = sec.iloc[0]
            info["股票代码"] = code
            info["股票简称"] = str(row.get("证券简称", code))
            info["上市日期"] = str(row.get("上市日期", ""))[:10]
            info["证券类型"] = str(row.get("证券类型", ""))
            info["交易所"] = str(row.get("交易所", ""))
            info["每手股数"] = str(row.get("每手股数", ""))
            info["沪港通"] = str(row.get("是否沪港通标的", ""))
            info["深港通"] = str(row.get("是否深港通标的", ""))
        try:
            with _bypass_proxy():
                comp = ak.stock_hk_company_profile_em(symbol=code)
            if not comp.empty:
                crow = comp.iloc[0]
                info["公司名称"] = str(crow.get("公司名称", ""))
                info["行业"] = str(crow.get("所属行业", ""))
                info["董事长"] = str(crow.get("董事长", ""))
                info["员工人数"] = str(crow.get("员工人数", ""))
                info["公司网址"] = str(crow.get("公司网址", ""))
        except Exception:
            pass
        return info if info else {"error": "未获取到港股基本信息"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# K 线
# ---------------------------------------------------------------------------

def fetch_daily_kline(
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取日 K 线数据（前复权），自动区分 A 股/港股."""
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    if is_hk_stock(code):
        return _fetch_daily_kline_hk(code, start_date, end_date, period, adjust)
    return _fetch_daily_kline_a(code, start_date, end_date, period, adjust)


def _fetch_daily_kline_a(
    code: str, start_date: str, end_date: str, period: str, adjust: str,
) -> pd.DataFrame:
    try:
        with _bypass_proxy():
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        return df
    except Exception:
        return _fetch_daily_kline_a_tx(code, start_date, end_date, adjust)


def _to_tx_symbol(code: str) -> str:
    """将纯数字股票代码转为腾讯格式 (sz/sh 前缀)."""
    if code.startswith(("sh", "sz")):
        return code
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


_TX_COL_MAP = {
    "date": "日期", "open": "开盘", "close": "收盘",
    "high": "最高", "low": "最低", "amount": "成交量",
}


def _fetch_daily_kline_a_tx(
    code: str, start_date: str, end_date: str, adjust: str,
) -> pd.DataFrame:
    """东方财富 K 线接口不可用时，降级到腾讯数据源."""
    import warnings
    warnings.warn(
        f"东方财富 K 线接口不可用，已降级到腾讯数据源 ({code})",
        stacklevel=3,
    )
    with _bypass_proxy():
        df = ak.stock_zh_a_hist_tx(
            symbol=_to_tx_symbol(code),
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    df.rename(columns=_TX_COL_MAP, inplace=True)
    return df


def _fetch_daily_kline_hk(
    code: str, start_date: str, end_date: str, period: str, adjust: str,
) -> pd.DataFrame:
    with _bypass_proxy():
        df = ak.stock_hk_hist(
            symbol=code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    return df


# ---------------------------------------------------------------------------
# 财务摘要
# ---------------------------------------------------------------------------

def fetch_financial_summary(code: str) -> pd.DataFrame:
    """获取最近的财务摘要数据."""
    if is_hk_stock(code):
        return _fetch_financial_summary_hk(code)
    return _fetch_financial_summary_a(code)


def _fetch_financial_summary_a(code: str) -> pd.DataFrame:
    try:
        with _bypass_proxy():
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
        return df.head(5)
    except Exception:
        try:
            with _bypass_proxy():
                df = ak.stock_financial_analysis_indicator(symbol=code)
            return df.head(5)
        except Exception:
            return pd.DataFrame()


def _fetch_financial_summary_hk(code: str) -> pd.DataFrame:
    try:
        with _bypass_proxy():
            df = ak.stock_financial_hk_analysis_indicator_em(symbol=code, indicator="年度")
        if df.empty:
            return pd.DataFrame()
        col_map = {
            "REPORT_DATE": "报告期",
            "OPERATE_INCOME": "营业收入",
            "OPERATE_INCOME_YOY": "营收同比(%)",
            "GROSS_PROFIT": "毛利",
            "GROSS_PROFIT_RATIO": "毛利率(%)",
            "HOLDER_PROFIT": "归母净利润",
            "HOLDER_PROFIT_YOY": "净利同比(%)",
            "NET_PROFIT_RATIO": "净利率(%)",
            "BASIC_EPS": "基本每股收益",
            "BPS": "每股净资产",
            "ROE_AVG": "ROE(%)",
            "ROA": "ROA(%)",
            "DEBT_ASSET_RATIO": "资产负债率(%)",
            "CURRENT_RATIO": "流动比率",
        }
        keep = [c for c in col_map if c in df.columns]
        result = df[keep].head(5).rename(columns=col_map)
        if "报告期" in result.columns:
            result["报告期"] = result["报告期"].astype(str).str[:10]
        for col in result.columns:
            if col == "报告期":
                continue
            if col in ("营业收入", "毛利", "归母净利润"):
                result[col] = result[col].apply(_fmt_amount)
            else:
                result[col] = result[col].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "N/A")
        return result
    except Exception:
        return pd.DataFrame()


def _fmt_amount(val) -> str:
    """将数值金额格式化为亿/万级别的可读字符串."""
    if pd.isna(val):
        return "N/A"
    v = float(val)
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.2f}万"
    return f"{v:.2f}"


# ---------------------------------------------------------------------------
# 估值
# ---------------------------------------------------------------------------

def fetch_valuation(code: str) -> dict:
    """获取当前估值指标."""
    if is_hk_stock(code):
        return _fetch_valuation_hk(code)
    return _fetch_valuation_a(code)


def _fetch_valuation_a(code: str) -> dict:
    try:
        with _bypass_proxy():
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


def _fetch_valuation_hk(code: str) -> dict:
    result: dict = {}
    indicators = {
        "市盈率(TTM)": "pe_ttm",
        "市盈率(静)": "pe",
        "市净率": "pb",
        "总市值": "total_mv",
    }
    for cn_name, key in indicators.items():
        try:
            with _bypass_proxy():
                df = ak.stock_hk_valuation_baidu(
                    symbol=code, indicator=cn_name, period="近一年",
                )
            if not df.empty:
                latest = df.iloc[-1]
                val = latest.get("value")
                if pd.notna(val):
                    result[key] = float(val)
        except Exception:
            continue
    return result


# ---------------------------------------------------------------------------
# 新闻
# ---------------------------------------------------------------------------

def fetch_news(code: str, limit: int = 10) -> list[dict]:
    """获取个股近期新闻."""
    try:
        with _bypass_proxy():
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
