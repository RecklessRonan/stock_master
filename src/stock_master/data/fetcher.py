"""AkShare 数据采集模块，支持 A 股与港股."""

from __future__ import annotations

import os
import time
import warnings
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
    """判断股票代码是否为港股.

    A 股代码固定 6 位数字；港股代码 5 位及以下。
    """
    return code.isdigit() and len(code) <= 5


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
    *,
    _max_retries: int = 3,
) -> pd.DataFrame:
    for attempt in range(_max_retries):
        try:
            with _bypass_proxy():
                df = ak.stock_hk_hist(
                    symbol=code,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
            return df
        except (ConnectionError, OSError) as e:
            if attempt < _max_retries - 1:
                wait = 2 ** attempt
                warnings.warn(
                    f"港股 K 线请求失败 ({code})，{wait}s 后重试 "
                    f"({attempt + 1}/{_max_retries}): {e}",
                    stacklevel=2,
                )
                time.sleep(wait)
            else:
                warnings.warn(
                    f"港股 K 线请求最终失败 ({code})，已重试 {_max_retries} 次: {e}",
                    stacklevel=2,
                )
                return _fetch_daily_kline_hk_fallback(code, adjust)
        except Exception as e:
            warnings.warn(f"港股 K 线数据获取异常 ({code}): {e}", stacklevel=2)
            return _fetch_daily_kline_hk_fallback(code, adjust)
    return _fetch_daily_kline_hk_fallback(code, adjust)


def _fetch_daily_kline_hk_fallback(code: str, adjust: str = "qfq") -> pd.DataFrame:
    """港股 K 线第二数据源 fallback."""
    try:
        with _bypass_proxy():
            df = ak.stock_hk_daily(symbol=code, adjust=adjust)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


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


def fetch_valuation_history(code: str) -> pd.DataFrame:
    """获取估值历史序列，用于计算历史分位."""
    if is_hk_stock(code):
        return _fetch_valuation_history_hk(code)
    return _fetch_valuation_history_a(code)


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


def _fetch_valuation_history_a(code: str) -> pd.DataFrame:
    try:
        with _bypass_proxy():
            df = ak.stock_a_indicator_lg(symbol=code)
        if df.empty:
            return pd.DataFrame()
        keep = [col for col in ("trade_date", "pe", "pe_ttm", "pb", "ps", "ps_ttm") if col in df.columns]
        result = df[keep].copy()
        if "trade_date" in result.columns:
            result.rename(columns={"trade_date": "date"}, inplace=True)
        return result.tail(756).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


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


def _fetch_valuation_history_hk(code: str) -> pd.DataFrame:
    frames = []
    indicators = {
        "市盈率(TTM)": "pe_ttm",
        "市盈率(静)": "pe",
        "市净率": "pb",
    }
    for cn_name, key in indicators.items():
        try:
            with _bypass_proxy():
                df = ak.stock_hk_valuation_baidu(
                    symbol=code,
                    indicator=cn_name,
                    period="近一年",
                )
            if df.empty or "date" not in df.columns or "value" not in df.columns:
                continue
            subset = df[["date", "value"]].copy()
            subset.rename(columns={"value": key}, inplace=True)
            frames.append(subset)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()

    result = frames[0]
    for frame in frames[1:]:
        result = result.merge(frame, on="date", how="outer")
    return result.sort_values("date").reset_index(drop=True)


def fetch_macro_snapshot(code: str = "", info: Optional[dict] = None) -> dict:
    """获取简要宏观快照.

    包含 CPI、PMI、GDP、M2 等宏观指标。
    每个数据源独立 try/except，部分成功也返回结果。
    """
    result: dict = {}
    headline_parts: list[str] = []

    try:
        with _bypass_proxy():
            cpi = ak.macro_china_cpi_yearly()
        if not cpi.empty:
            latest_cpi = cpi.iloc[-1].to_dict()
            headline_parts.append(f"CPI {latest_cpi}")
    except Exception:
        pass

    try:
        with _bypass_proxy():
            pmi = ak.macro_china_pmi_yearly()
        if not pmi.empty:
            latest_pmi = pmi.iloc[-1].to_dict()
            headline_parts.append(f"PMI {latest_pmi}")
    except Exception:
        pass

    try:
        with _bypass_proxy():
            gdp = ak.macro_china_gdp_yearly()
        if not gdp.empty:
            latest_gdp = gdp.iloc[-1].to_dict()
            result["gdp"] = latest_gdp
            headline_parts.append(f"GDP {latest_gdp}")
    except Exception:
        pass

    try:
        with _bypass_proxy():
            m2 = ak.macro_china_money_supply()
        if not m2.empty:
            latest_m2 = m2.iloc[-1].to_dict()
            result["m2"] = latest_m2
            headline_parts.append(f"M2 {latest_m2}")
    except Exception:
        pass

    if headline_parts:
        result.update({
            "market_regime": "宏观跟踪中",
            "policy_bias": "待人工确认",
            "liquidity": "待人工确认",
            "headline": "；".join(headline_parts),
        })
    return result


def fetch_peer_benchmark(code: str, info: Optional[dict] = None, limit: int = 5) -> list[dict]:
    """获取同行估值对比.

    尝试通过行业成分股接口获取同行数据并拉取基础估值。
    接口不可用时降级为仅返回自身条目或空列表。
    """
    industry = ""
    if info:
        industry = str(info.get("行业", "")).strip()
    if not industry:
        return []

    try:
        with _bypass_proxy():
            cons = ak.stock_board_industry_cons_em(symbol=industry)
        if cons.empty:
            raise ValueError("empty")
        peers: list[dict] = []
        code_col = None
        for candidate in ("代码", "股票代码", "code"):
            if candidate in cons.columns:
                code_col = candidate
                break
        name_col = None
        for candidate in ("名称", "股票简称", "name"):
            if candidate in cons.columns:
                name_col = candidate
                break
        if code_col is None:
            raise ValueError("no code column")

        peer_codes = [
            str(r) for r in cons[code_col].tolist()
            if str(r) != code
        ][:limit]

        for pc in peer_codes:
            entry: dict = {
                "code": pc,
                "name": cons.loc[cons[code_col] == pc, name_col].iloc[0] if name_col else pc,
                "industry": industry,
                "pe": None,
                "pb": None,
                "market_cap": None,
            }
            try:
                val = fetch_valuation(pc)
                entry["pe"] = val.get("pe") or val.get("pe_ttm")
                entry["pb"] = val.get("pb")
                entry["market_cap"] = val.get("total_mv")
            except Exception:
                pass
            peers.append(entry)
        return peers[:limit]
    except Exception:
        fallback = {"code": code, "name": info.get("股票简称", code) if info else code, "industry": industry}
        return [fallback][:limit]


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


# ---------------------------------------------------------------------------
# 资金流向
# ---------------------------------------------------------------------------

def fetch_capital_flow(code: str) -> dict:
    """获取个股资金流向（主力/超大/大单净流入）.

    港股暂不支持，直接返回空 dict。
    """
    if is_hk_stock(code):
        return {}
    try:
        with _bypass_proxy():
            df = ak.stock_individual_fund_flow(stock=code, market="")
        if df is None or df.empty:
            raise ValueError("empty")
        latest = df.iloc[-1]
        return {
            "main_net_inflow": float(latest.get("主力净流入-净额", 0)),
            "super_large_net": float(latest.get("超大单净流入-净额", 0)),
            "large_net": float(latest.get("大单净流入-净额", 0)),
            "medium_net": float(latest.get("中单净流入-净额", 0)),
            "small_net": float(latest.get("小单净流入-净额", 0)),
        }
    except Exception:
        try:
            with _bypass_proxy():
                df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df is None or df.empty:
                return {}
            code_col = None
            for candidate in ("代码", "股票代码"):
                if candidate in df.columns:
                    code_col = candidate
                    break
            if code_col is None:
                return {}
            matched = df[df[code_col].astype(str) == code]
            if matched.empty:
                return {}
            row = matched.iloc[0]
            return {
                "main_net_inflow": float(row.get("主力净流入-净额", 0)),
                "super_large_net": float(row.get("超大单净流入-净额", 0)),
                "large_net": float(row.get("大单净流入-净额", 0)),
                "medium_net": float(row.get("中单净流入-净额", 0)),
                "small_net": float(row.get("小单净流入-净额", 0)),
            }
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# 北向/南向资金
# ---------------------------------------------------------------------------

def fetch_north_south_flow() -> dict:
    """获取北向/南向资金净流入最新数据."""
    result: dict = {}
    try:
        with _bypass_proxy():
            north = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if north is not None and not north.empty:
            latest = north.iloc[-1]
            date_val = latest.get("date", latest.get("日期", ""))
            value_val = latest.get("value", latest.get("当日净流入", 0))
            result["north_net_inflow"] = float(value_val) if pd.notna(value_val) else 0.0
            result["date"] = str(date_val)[:10] if pd.notna(date_val) else ""
    except Exception:
        pass

    try:
        with _bypass_proxy():
            south = ak.stock_hsgt_south_net_flow_in_em(symbol="南下")
        if south is not None and not south.empty:
            latest = south.iloc[-1]
            value_val = latest.get("value", latest.get("当日净流入", 0))
            result["south_net_inflow"] = float(value_val) if pd.notna(value_val) else 0.0
            if "date" not in result:
                date_val = latest.get("date", latest.get("日期", ""))
                result["date"] = str(date_val)[:10] if pd.notna(date_val) else ""
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# 十大流通股东变化
# ---------------------------------------------------------------------------

def fetch_shareholder_changes(code: str, limit: int = 4) -> list[dict]:
    """获取十大流通股东变化.

    港股暂不支持，直接返回空列表。
    """
    if is_hk_stock(code):
        return []
    try:
        with _bypass_proxy():
            df = ak.stock_gdfx_free_holding_analyse_em(symbol=code)
        if df is not None and not df.empty:
            return _parse_shareholder_df(df, limit)
    except Exception:
        pass
    try:
        with _bypass_proxy():
            df = ak.stock_gdfx_free_top_10_em(symbol=code)
        if df is not None and not df.empty:
            return _parse_shareholder_df(df, limit)
    except Exception:
        pass
    return []


def _parse_shareholder_df(df: pd.DataFrame, limit: int) -> list[dict]:
    """从股东 DataFrame 解析标准化结果."""
    results: list[dict] = []
    for _, row in df.head(limit).iterrows():
        holder = str(row.get("股东名称", row.get("holder", "")))
        shares = row.get("持股数量", row.get("持股数", row.get("shares", 0)))
        change = row.get("增减比例", row.get("变动比例", row.get("change_pct", 0)))
        report_date = str(row.get("报告期", row.get("截止日期", row.get("report_date", ""))))[:10]
        results.append({
            "holder": holder,
            "shares": float(shares) if pd.notna(shares) else 0.0,
            "change_pct": float(change) if pd.notna(change) else 0.0,
            "report_date": report_date,
        })
    return results


# ---------------------------------------------------------------------------
# 公司公告
# ---------------------------------------------------------------------------

def fetch_announcements(code: str, limit: int = 10) -> list[dict]:
    """获取公司公告列表."""
    try:
        with _bypass_proxy():
            df = ak.stock_notice_report(symbol=code)
        if df is None or df.empty:
            return []
        results: list[dict] = []
        for _, row in df.head(limit).iterrows():
            results.append({
                "title": str(row.get("公告标题", row.get("title", ""))),
                "date": str(row.get("公告日期", row.get("date", "")))[:10],
                "type": str(row.get("公告类型", row.get("type", ""))),
                "url": str(row.get("公告链接", row.get("url", ""))),
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 业绩预告/快报
# ---------------------------------------------------------------------------

def fetch_earnings_forecast(code: str) -> list[dict]:
    """获取业绩预告/快报.

    尝试获取当前季度的业绩预告数据并按股票代码过滤。
    """
    if is_hk_stock(code):
        return []

    now = datetime.now()
    year = now.year
    quarter = (now.month - 1) // 3 + 1
    quarter_dates = {1: f"{year}0331", 2: f"{year}0630", 3: f"{year}0930", 4: f"{year}1231"}
    date_str = quarter_dates[quarter]

    try:
        with _bypass_proxy():
            df = ak.stock_yjyg_em(date=date_str)
        if df is None or df.empty:
            return []
        code_col = None
        for candidate in ("股票代码", "代码", "code"):
            if candidate in df.columns:
                code_col = candidate
                break
        if code_col is None:
            return []
        matched = df[df[code_col].astype(str).str.strip() == code]
        if matched.empty:
            return []
        results: list[dict] = []
        for _, row in matched.iterrows():
            results.append({
                "report_period": str(row.get("报告期", row.get("业绩预告期", "")))[:10],
                "forecast_type": str(row.get("预告类型", row.get("业绩变动类型", ""))),
                "net_profit_min": float(row.get("预告净利润下限", 0)) if pd.notna(row.get("预告净利润下限")) else 0.0,
                "net_profit_max": float(row.get("预告净利润上限", 0)) if pd.notna(row.get("预告净利润上限")) else 0.0,
                "change_pct_min": float(row.get("预告净利润变动幅度下限", 0)) if pd.notna(row.get("预告净利润变动幅度下限")) else 0.0,
                "change_pct_max": float(row.get("预告净利润变动幅度上限", 0)) if pd.notna(row.get("预告净利润变动幅度上限")) else 0.0,
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 完整三表
# ---------------------------------------------------------------------------

def fetch_financial_statements(code: str) -> dict:
    """获取完整三表核心指标（资产负债表/利润表/现金流量表，各取最近5期）.

    港股暂不支持，返回全 None。
    """
    if is_hk_stock(code):
        return {"balance_sheet": None, "income_statement": None, "cash_flow": None}

    result: dict = {"balance_sheet": None, "income_statement": None, "cash_flow": None}

    statement_map = {
        "balance_sheet": "资产负债表",
        "income_statement": "利润表",
        "cash_flow": "现金流量表",
    }
    for key, symbol in statement_map.items():
        try:
            with _bypass_proxy():
                df = ak.stock_financial_report_sina(stock=code, symbol=symbol)
            if df is not None and not df.empty:
                result[key] = df.head(5).to_dict(orient="records")
        except Exception:
            pass

    return result
