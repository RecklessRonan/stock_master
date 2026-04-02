"""证据覆盖度增强测试."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from stock_master.analysis.quantitative import compute_score, FactorScore, ScoreResult
from stock_master.pipeline.dossier import _build_coverage, _detect_stale, generate_teaching_segment, build_stock_dossier


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sample_kline(rows: int = 80):
    closes = [20 + i * 0.15 for i in range(rows)]
    frame = pd.DataFrame({
        "收盘": closes,
        "最高": [c + 0.25 for c in closes],
        "最低": [c - 0.25 for c in closes],
        "成交量": [3000 + i * 20 for i in range(rows)],
    })
    frame["MA20"] = frame["收盘"].rolling(20).mean().bfill()
    frame["RSI14"] = 55.0
    return frame


def _sample_financial():
    return pd.DataFrame([{
        "报告期": "2025-12-31",
        "ROE(%)": 16.0,
        "毛利率(%)": 40.0,
        "净利率(%)": 18.0,
        "营收同比(%)": 20.0,
        "净利同比(%)": 25.0,
        "资产负债率(%)": 30.0,
        "流动比率": 1.8,
    }])


def _sample_score():
    return compute_score(
        _sample_kline(),
        {"pe_ttm": 16.0, "pb": 2.4},
        financial=_sample_financial(),
        valuation_history=pd.DataFrame({"pe_ttm": [10, 12, 14, 16, 18, 20]}),
        news=[{"title": "回购", "content": "计划回购"}],
    )


# ---------------------------------------------------------------------------
# _build_coverage
# ---------------------------------------------------------------------------

def test_coverage_13_sections():
    coverage = _build_coverage(
        info={"股票简称": "测试"},
        kline=_sample_kline(),
        valuation={"pe_ttm": 16},
        financial=_sample_financial(),
        news=[{"title": "新闻", "time": "2026-04-01"}],
        macro={"headline": "GDP 2026"},
        peers=[{"code": "300001"}],
        capital_flow={"main_net_inflow": 1000},
        shareholder_changes=[{"holder": "张三"}],
        announcements=[{"title": "公告"}],
        earnings_forecast=[{"type": "预增"}],
        financial_statements={"balance_sheet": pd.DataFrame([{"资产": 1}]), "income_statement": None, "cash_flow": None},
        valuation_history=pd.DataFrame({"pe_ttm": [10, 12, 14]}),
    )

    assert len(coverage.available_sections) + len(coverage.missing_sections) == 13
    assert coverage.coverage_ratio > 0.9


def test_coverage_with_missing():
    coverage = _build_coverage(
        info={"股票简称": "测试"},
        kline=_sample_kline(),
        valuation={"pe_ttm": 16},
        financial=None,
        news=[],
        macro={},
        peers=[],
        capital_flow=None,
        shareholder_changes=None,
        announcements=None,
        earnings_forecast=None,
        financial_statements=None,
        valuation_history=None,
    )

    assert len(coverage.missing_sections) >= 5
    assert coverage.coverage_ratio < 0.5


# ---------------------------------------------------------------------------
# _detect_stale
# ---------------------------------------------------------------------------

def test_stale_detection_kline():
    old_kline = pd.DataFrame({
        "日期": [(datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")],
        "收盘": [20.0],
    })
    stale = _detect_stale(kline=old_kline, news=[], macro={})
    assert "行情" in stale


def test_stale_detection_news():
    old_news = [{"title": "旧闻", "time": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")}]
    stale = _detect_stale(kline=pd.DataFrame(), news=old_news, macro={})
    assert "新闻" in stale


def test_stale_detection_macro():
    stale = _detect_stale(
        kline=pd.DataFrame(),
        news=[],
        macro={"headline": "GDP 2020 数据"},
    )
    assert "宏观" in stale


# ---------------------------------------------------------------------------
# generate_teaching_segment
# ---------------------------------------------------------------------------

def test_teaching_segment_generation():
    score = _sample_score()
    from stock_master.models.research import EvidenceCoverage
    coverage = EvidenceCoverage(
        available_sections=["基本信息", "行情", "估值"],
        missing_sections=["新闻", "宏观"],
        stale_sections=[],
        coverage_ratio=0.6,
    )

    text = generate_teaching_segment(score, coverage)
    assert len(text) > 0
    assert "覆盖度" in text


# ---------------------------------------------------------------------------
# build_stock_dossier with all new data types
# ---------------------------------------------------------------------------

def test_dossier_with_all_new_data():
    score = _sample_score()

    dossier = build_stock_dossier(
        code="300999",
        stock_name="测试股份",
        score=score,
        info={"股票简称": "测试股份", "行业": "软件服务"},
        kline=_sample_kline(),
        valuation={"pe_ttm": 16.0, "pb": 2.4},
        financial=_sample_financial(),
        news=[{"title": "回购公告", "content": "计划回购", "time": "2026-04-01", "source": "东财"}],
        macro={"headline": "GDP 2026 稳增长", "gdp": {}},
        peers=[{"code": "300001", "name": "同业A", "pe_ttm": 20}],
        capital_flow={"main_net_inflow": 5000},
        shareholder_changes=[{"holder": "机构A", "shares": 1000000}],
        announcements=[{"title": "回购公告", "date": "2026-04-01"}],
        earnings_forecast=[{"type": "预增", "report_period": "2026-03-31"}],
        financial_statements={"balance_sheet": pd.DataFrame([{"总资产": 1e10}]), "income_statement": None, "cash_flow": None},
        valuation_history=pd.DataFrame({"pe_ttm": [10, 12, 14, 16, 18]}),
    )

    assert dossier.code == "300999"
    assert dossier.capital_flow["main_net_inflow"] == 5000
    assert len(dossier.shareholder_changes) == 1
    assert len(dossier.announcements) == 1
    assert len(dossier.earnings_forecast) == 1
    assert dossier.coverage.coverage_ratio > 0.8
    assert dossier.rookie_action.verdict is not None
