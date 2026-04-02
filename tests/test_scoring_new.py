"""评分增强测试."""
from __future__ import annotations

import pandas as pd
import pytest

from stock_master.analysis.quantitative import compute_score, score_quality, score_value, FactorScore


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


# ---------------------------------------------------------------------------
# sub_factors populated
# ---------------------------------------------------------------------------

def test_sub_factors_populated():
    factor = score_quality(_sample_financial())
    assert factor.sub_factors, "score_quality 应返回非空 sub_factors"
    for sf in factor.sub_factors:
        assert "name" in sf
        assert "score" in sf
        assert "explanation" in sf


# ---------------------------------------------------------------------------
# factor_confidence when ok
# ---------------------------------------------------------------------------

def test_factor_confidence_ok():
    factor = score_quality(_sample_financial())
    assert factor.status == "ok"
    assert factor.confidence > 0


# ---------------------------------------------------------------------------
# factor_confidence when missing
# ---------------------------------------------------------------------------

def test_factor_confidence_missing():
    factor = score_quality(None)
    assert factor.status == "missing"
    assert factor.confidence == 0.0


# ---------------------------------------------------------------------------
# peer_percentile in value factor
# ---------------------------------------------------------------------------

def test_peer_percentile_in_value():
    valuation = {"pe_ttm": 16.0, "pb": 2.4}
    factor = score_value(valuation, peer_percentile=30.0)

    assert factor.peer_percentile == 30.0
    assert "同行PE分位" in factor.metrics
    has_peer_sub = any(sf["name"] == "同行PE分位" for sf in factor.sub_factors)
    assert has_peer_sub


# ---------------------------------------------------------------------------
# compute_score with peers
# ---------------------------------------------------------------------------

def test_compute_score_with_peers():
    kline = _sample_kline()
    valuation = {"pe_ttm": 16.0, "pb": 2.4}
    financial = _sample_financial()
    val_history = pd.DataFrame({"pe_ttm": [10, 12, 14, 16, 18, 20]})
    peers = [
        {"code": "300001", "pe_ttm": 20.0},
        {"code": "300002", "pe_ttm": 25.0},
        {"code": "300003", "pe_ttm": 12.0},
    ]

    result = compute_score(
        kline,
        valuation,
        financial=financial,
        valuation_history=val_history,
        news=[{"title": "增长", "content": "业绩增长"}],
        peers=peers,
    )

    assert result.overall > 0
    assert result.confidence > 0

    val_factor = result.factors["估值"]
    assert val_factor.status == "ok"
    assert val_factor.peer_percentile is not None
