"""组合风控增强测试."""
from __future__ import annotations

import pytest

from stock_master.portfolio.guardrails import (
    check_industry_concentration,
    check_drawdown,
    check_cash_ratio,
    suggest_rebalance,
    check_chasing_high,
    check_homogeneity,
    comprehensive_portfolio_analysis,
    evaluate_buy_candidate,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _make_portfolio(positions, cash=100_000.0):
    return {"positions": positions, "cash": cash}


# ---------------------------------------------------------------------------
# 行业集中度
# ---------------------------------------------------------------------------

def test_industry_concentration_warns():
    portfolio = _make_portfolio([
        {"code": "600519", "industry": "白酒", "shares": 100, "current_price": 1800},
        {"code": "000858", "industry": "白酒", "shares": 200, "current_price": 150},
        {"code": "601318", "industry": "保险", "shares": 50, "current_price": 60},
    ], cash=10_000)

    result = check_industry_concentration(portfolio)
    assert result["warnings"], "同行业占比超 40% 应有警告"
    assert result["max_industry_pct"] > 40


def test_industry_concentration_ok():
    portfolio = _make_portfolio([
        {"code": "600519", "industry": "白酒", "shares": 10, "current_price": 100},
        {"code": "601318", "industry": "保险", "shares": 10, "current_price": 100},
        {"code": "000001", "industry": "银行", "shares": 10, "current_price": 100},
    ], cash=10_000)

    result = check_industry_concentration(portfolio)
    assert not result["warnings"]


# ---------------------------------------------------------------------------
# 回撤
# ---------------------------------------------------------------------------

def test_drawdown_warns():
    portfolio = _make_portfolio([
        {"code": "600519", "avg_cost": 100, "current_price": 80, "shares": 100},
    ], cash=50_000)

    result = check_drawdown(portfolio)
    assert result["warnings"], "浮亏 20% 应触发警告"
    assert result["position_drawdowns"]["600519"] < -15


def test_drawdown_ok():
    portfolio = _make_portfolio([
        {"code": "600519", "avg_cost": 100, "current_price": 95, "shares": 100},
    ], cash=50_000)

    result = check_drawdown(portfolio)
    assert not result["warnings"]


# ---------------------------------------------------------------------------
# 现金比例
# ---------------------------------------------------------------------------

def test_cash_ratio_warns():
    portfolio = _make_portfolio([
        {"code": "600519", "shares": 100, "current_price": 100},
    ], cash=1_000)

    result = check_cash_ratio(portfolio)
    assert result["warnings"], "现金占比不到 20% 应有警告"
    assert result["cash_pct"] < 20


def test_cash_ratio_ok():
    portfolio = _make_portfolio([
        {"code": "600519", "shares": 10, "current_price": 100},
    ], cash=50_000)

    result = check_cash_ratio(portfolio)
    assert not result["warnings"]


# ---------------------------------------------------------------------------
# 再平衡
# ---------------------------------------------------------------------------

def test_rebalance_needed():
    portfolio = _make_portfolio([
        {"code": "600519", "shares": 100, "current_price": 100, "target_pct": 20},
    ], cash=10_000)

    result = suggest_rebalance(portfolio)
    assert result["needs_rebalance"]
    assert len(result["deviations"]) > 0


def test_rebalance_not_needed():
    portfolio = _make_portfolio([
        {"code": "600519", "shares": 10, "current_price": 100, "target_pct": 50},
    ], cash=1_000)

    result = suggest_rebalance(portfolio)
    assert not result["needs_rebalance"]


# ---------------------------------------------------------------------------
# 追涨检测
# ---------------------------------------------------------------------------

def test_chasing_high_warns():
    kline_data = {"recent_high": 100, "current_price": 98, "pct_from_high": 18}
    result = check_chasing_high("600519", kline_data)

    assert result["is_chasing"]
    assert len(result["warnings"]) > 0


def test_chasing_high_ok():
    kline_data = {"recent_high": 100, "current_price": 80, "pct_from_high": 5}
    result = check_chasing_high("600519", kline_data)

    assert not result["is_chasing"]
    assert len(result["warnings"]) == 0


# ---------------------------------------------------------------------------
# 同质检测
# ---------------------------------------------------------------------------

def test_homogeneity_same_industry():
    portfolio = _make_portfolio([
        {"code": "000858", "industry": "白酒", "shares": 100, "current_price": 150},
    ])
    candidate_info = {"industry": "白酒", "concepts": []}

    result = check_homogeneity(portfolio, "600519", candidate_info)
    assert result["is_homogeneous"]
    assert "白酒" in result["warnings"][0]


def test_homogeneity_different_industry():
    portfolio = _make_portfolio([
        {"code": "601318", "industry": "保险", "shares": 100, "current_price": 60},
    ])
    candidate_info = {"industry": "白酒", "concepts": []}

    result = check_homogeneity(portfolio, "600519", candidate_info)
    assert not result["is_homogeneous"]
    assert len(result["warnings"]) == 0


# ---------------------------------------------------------------------------
# 综合风控
# ---------------------------------------------------------------------------

def test_comprehensive_includes_all():
    portfolio = _make_portfolio([
        {"code": "600519", "industry": "白酒", "avg_cost": 100, "current_price": 70,
         "shares": 500, "target_pct": 10},
        {"code": "000858", "industry": "白酒", "avg_cost": 50, "current_price": 45,
         "shares": 200, "target_pct": 10},
    ], cash=1_000)

    result = comprehensive_portfolio_analysis(portfolio)
    assert "risk_level" in result
    assert "guardrails" in result
    assert "industry_concentration" in result
    assert "drawdown" in result
    assert "cash_ratio" in result
    assert "rebalance" in result
    assert result["total_warnings"] >= 1


# ---------------------------------------------------------------------------
# 增强版 evaluate_buy_candidate
# ---------------------------------------------------------------------------

def test_evaluate_buy_enhanced():
    portfolio = _make_portfolio([
        {"code": "000858", "industry": "白酒", "shares": 100, "current_price": 150},
    ], cash=50_000)

    candidate = {"code": "600519", "name": "贵州茅台", "planned_position_pct": 8.0}
    kline_data = {"recent_high": 2000, "current_price": 1960, "pct_from_high": 5}
    candidate_info = {"industry": "白酒", "concepts": ["消费"]}

    result = evaluate_buy_candidate(
        portfolio,
        candidate,
        kline_data=kline_data,
        candidate_info=candidate_info,
    )

    assert result["code"] == "600519"
    assert result["chasing_check"] is not None
    assert result["homogeneity_check"] is not None
    assert result["homogeneity_check"]["is_homogeneous"]
    assert any("白酒" in w for w in result["warnings"])
