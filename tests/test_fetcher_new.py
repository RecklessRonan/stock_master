"""新增数据获取函数测试."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _capital_flow_df():
    return pd.DataFrame([{
        "主力净流入-净额": 12345.0,
        "超大单净流入-净额": 5000.0,
        "大单净流入-净额": 7345.0,
        "中单净流入-净额": -2000.0,
        "小单净流入-净额": -3000.0,
    }])


def _capital_flow_rank_df(code: str = "600519"):
    return pd.DataFrame([{
        "代码": code,
        "主力净流入-净额": 9999.0,
        "超大单净流入-净额": 4000.0,
        "大单净流入-净额": 5999.0,
        "中单净流入-净额": -1000.0,
        "小单净流入-净额": -2000.0,
    }])


def _north_df():
    return pd.DataFrame([{"date": "2026-04-01", "value": 5678.0}])


def _south_df():
    return pd.DataFrame([{"date": "2026-04-01", "value": -1234.0}])


def _shareholder_df():
    return pd.DataFrame([
        {"股东名称": "张三", "持股数量": 1_000_000, "增减比例": 5.0, "报告期": "2026-03-31"},
        {"股东名称": "李四", "持股数量": 800_000, "增减比例": -2.0, "报告期": "2026-03-31"},
    ])


def _announcement_df():
    return pd.DataFrame([
        {"公告标题": "关于回购股份的公告", "公告日期": "2026-04-01", "公告类型": "股权", "公告链接": "http://example.com/1"},
        {"公告标题": "2025年度报告", "公告日期": "2026-03-28", "公告类型": "年报", "公告链接": "http://example.com/2"},
    ])


def _earnings_forecast_df(code: str = "600519"):
    return pd.DataFrame([{
        "股票代码": code,
        "报告期": "2026-03-31",
        "预告类型": "预增",
        "预告净利润下限": 1e8,
        "预告净利润上限": 1.5e8,
        "预告净利润变动幅度下限": 20.0,
        "预告净利润变动幅度上限": 50.0,
    }])


def _financial_report_df():
    return pd.DataFrame([{"报告期": "2025-12-31", "总资产": 1e10, "净资产": 5e9}])


def _industry_cons_df():
    return pd.DataFrame([
        {"代码": "600519", "名称": "贵州茅台"},
        {"代码": "000858", "名称": "五粮液"},
        {"代码": "000568", "名称": "泸州老窖"},
    ])


# ---------------------------------------------------------------------------
# test_fetch_capital_flow_a_stock
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_individual_fund_flow")
def test_fetch_capital_flow_a_stock(mock_fund_flow):
    from stock_master.data.fetcher import fetch_capital_flow

    mock_fund_flow.return_value = _capital_flow_df()
    result = fetch_capital_flow("600519")

    assert isinstance(result, dict)
    assert result["main_net_inflow"] == 12345.0
    assert result["super_large_net"] == 5000.0
    assert result["large_net"] == 7345.0
    mock_fund_flow.assert_called_once()


# ---------------------------------------------------------------------------
# test_fetch_capital_flow_hk_returns_empty
# ---------------------------------------------------------------------------

def test_fetch_capital_flow_hk_returns_empty():
    from stock_master.data.fetcher import fetch_capital_flow

    result = fetch_capital_flow("00700")
    assert result == {}


# ---------------------------------------------------------------------------
# test_fetch_capital_flow_fallback
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_individual_fund_flow_rank")
@patch("stock_master.data.fetcher.ak.stock_individual_fund_flow")
def test_fetch_capital_flow_fallback(mock_primary, mock_fallback):
    from stock_master.data.fetcher import fetch_capital_flow

    mock_primary.side_effect = Exception("primary failed")
    mock_fallback.return_value = _capital_flow_rank_df("600519")

    result = fetch_capital_flow("600519")
    assert result["main_net_inflow"] == 9999.0
    mock_primary.assert_called_once()
    mock_fallback.assert_called_once()


# ---------------------------------------------------------------------------
# test_fetch_capital_flow_all_fail
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_individual_fund_flow_rank")
@patch("stock_master.data.fetcher.ak.stock_individual_fund_flow")
def test_fetch_capital_flow_all_fail(mock_primary, mock_fallback):
    from stock_master.data.fetcher import fetch_capital_flow

    mock_primary.side_effect = Exception("fail")
    mock_fallback.side_effect = Exception("fail")

    result = fetch_capital_flow("600519")
    assert result == {}


# ---------------------------------------------------------------------------
# test_fetch_north_south_flow
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_hsgt_south_net_flow_in_em", create=True)
@patch("stock_master.data.fetcher.ak.stock_hsgt_north_net_flow_in_em", create=True)
def test_fetch_north_south_flow(mock_north, mock_south):
    from stock_master.data.fetcher import fetch_north_south_flow

    mock_north.return_value = _north_df()
    mock_south.return_value = _south_df()

    result = fetch_north_south_flow()
    assert result["north_net_inflow"] == 5678.0
    assert result["south_net_inflow"] == -1234.0
    assert result["date"] == "2026-04-01"


# ---------------------------------------------------------------------------
# test_fetch_shareholder_changes_a_stock
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_gdfx_free_holding_analyse_em")
def test_fetch_shareholder_changes_a_stock(mock_sh):
    from stock_master.data.fetcher import fetch_shareholder_changes

    mock_sh.return_value = _shareholder_df()
    result = fetch_shareholder_changes("600519")

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["holder"] == "张三"
    assert result[0]["shares"] == 1_000_000.0


# ---------------------------------------------------------------------------
# test_fetch_shareholder_changes_hk_returns_empty
# ---------------------------------------------------------------------------

def test_fetch_shareholder_changes_hk_returns_empty():
    from stock_master.data.fetcher import fetch_shareholder_changes

    result = fetch_shareholder_changes("00700")
    assert result == []


# ---------------------------------------------------------------------------
# test_fetch_announcements
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_notice_report")
def test_fetch_announcements(mock_notice):
    from stock_master.data.fetcher import fetch_announcements

    mock_notice.return_value = _announcement_df()
    result = fetch_announcements("600519")

    assert isinstance(result, list)
    assert len(result) == 2
    assert "回购" in result[0]["title"]


# ---------------------------------------------------------------------------
# test_fetch_earnings_forecast
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_yjyg_em")
def test_fetch_earnings_forecast(mock_yjyg):
    from stock_master.data.fetcher import fetch_earnings_forecast

    mock_yjyg.return_value = _earnings_forecast_df("600519")
    result = fetch_earnings_forecast("600519")

    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["forecast_type"] == "预增"
    assert result[0]["net_profit_min"] == 1e8


# ---------------------------------------------------------------------------
# test_fetch_financial_statements
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.stock_financial_report_sina")
def test_fetch_financial_statements(mock_report):
    from stock_master.data.fetcher import fetch_financial_statements

    mock_report.return_value = _financial_report_df()
    result = fetch_financial_statements("600519")

    assert "balance_sheet" in result
    assert "income_statement" in result
    assert "cash_flow" in result
    assert mock_report.call_count == 3


# ---------------------------------------------------------------------------
# test_fetch_financial_statements_hk
# ---------------------------------------------------------------------------

def test_fetch_financial_statements_hk():
    from stock_master.data.fetcher import fetch_financial_statements

    result = fetch_financial_statements("00700")
    assert result["balance_sheet"] is None
    assert result["income_statement"] is None
    assert result["cash_flow"] is None


# ---------------------------------------------------------------------------
# test_fetch_peer_benchmark_enhanced
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.fetch_valuation")
@patch("stock_master.data.fetcher.ak.stock_board_industry_cons_em")
def test_fetch_peer_benchmark_enhanced(mock_cons, mock_val):
    from stock_master.data.fetcher import fetch_peer_benchmark

    mock_cons.return_value = _industry_cons_df()
    mock_val.return_value = {"pe_ttm": 25.0, "pb": 3.5, "total_mv": 5000}

    result = fetch_peer_benchmark("600519", info={"行业": "白酒"}, limit=5)

    assert isinstance(result, list)
    assert len(result) >= 1
    for peer in result:
        assert "code" in peer
        assert "name" in peer


# ---------------------------------------------------------------------------
# test_fetch_macro_snapshot_enhanced
# ---------------------------------------------------------------------------

@patch("stock_master.data.fetcher.ak.macro_china_money_supply")
@patch("stock_master.data.fetcher.ak.macro_china_gdp_yearly")
@patch("stock_master.data.fetcher.ak.macro_china_pmi_yearly")
@patch("stock_master.data.fetcher.ak.macro_china_cpi_yearly")
def test_fetch_macro_snapshot_enhanced(mock_cpi, mock_pmi, mock_gdp, mock_m2):
    from stock_master.data.fetcher import fetch_macro_snapshot

    mock_cpi.return_value = pd.DataFrame([{"date": "2026-03", "value": 101.5}])
    mock_pmi.return_value = pd.DataFrame([{"date": "2026-03", "value": 50.2}])
    mock_gdp.return_value = pd.DataFrame([{"date": "2025", "value": 130e12}])
    mock_m2.return_value = pd.DataFrame([{"date": "2026-03", "value": 320e12}])

    result = fetch_macro_snapshot()

    assert "gdp" in result
    assert "m2" in result
    assert "headline" in result
    assert "GDP" in result["headline"]
    assert "M2" in result["headline"]
