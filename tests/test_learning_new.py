"""学习模块增强测试."""
from __future__ import annotations

from unittest.mock import patch
from pathlib import Path

import pytest

from stock_master.portfolio.learning import (
    detect_behavioral_biases,
    build_trader_profile,
    load_personal_rules,
    save_personal_rule,
    suggest_rules_from_history,
    build_learning_report,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _trades_overtrading():
    """同月 5 笔交易，触发过度交易."""
    return [
        {"code": "600519", "action": "buy", "date": "2026-03-01", "price": 100, "research_ref": "r1"},
        {"code": "600519", "action": "sell", "date": "2026-03-05", "price": 105, "buy_price": 100, "research_ref": "r2"},
        {"code": "000858", "action": "buy", "date": "2026-03-10", "price": 50, "research_ref": "r3"},
        {"code": "000858", "action": "sell", "date": "2026-03-15", "price": 48, "buy_price": 50, "research_ref": "r4"},
        {"code": "601318", "action": "buy", "date": "2026-03-20", "price": 60, "research_ref": "r5"},
    ]


def _trades_attention_driven():
    """所有交易无 research_ref."""
    return [
        {"code": "600519", "action": "buy", "date": "2026-03-01", "price": 100},
        {"code": "600519", "action": "sell", "date": "2026-03-05", "price": 105, "buy_price": 100},
    ]


def _trades_clean():
    """少量高质量交易."""
    return [
        {"code": "600519", "action": "buy", "date": "2026-01-15", "price": 100, "research_ref": "r1"},
        {"code": "600519", "action": "sell", "date": "2026-03-15", "price": 120, "buy_price": 100,
         "buy_date": "2026-01-15", "research_ref": "r1", "review_date": "2026-03-20"},
    ]


def _empty_portfolio():
    return {"positions": [], "cash": 1_000_000}


# ---------------------------------------------------------------------------
# detect_behavioral_biases
# ---------------------------------------------------------------------------

def test_detect_overtrading():
    biases = detect_behavioral_biases(_trades_overtrading(), _empty_portfolio())
    types = [b["bias_type"] for b in biases]
    assert "过度交易" in types


def test_detect_attention_driven():
    biases = detect_behavioral_biases(_trades_attention_driven(), _empty_portfolio())
    types = [b["bias_type"] for b in biases]
    assert "注意力驱动" in types


def test_detect_no_biases():
    biases = detect_behavioral_biases(_trades_clean(), _empty_portfolio())
    harmful = [b for b in biases if b["bias_type"] in ("过度交易", "注意力驱动")]
    assert not harmful


# ---------------------------------------------------------------------------
# build_trader_profile
# ---------------------------------------------------------------------------

def test_trader_profile_basic():
    trades = _trades_clean()
    reviews = [{"code": "600519", "date": "2026-03-20", "content": "表现良好"}]

    profile = build_trader_profile(trades, reviews)

    assert profile["total_trades"] == 2
    assert profile["win_rate"] == 100.0
    assert profile["avg_holding_days"] > 0
    assert isinstance(profile["recommendations"], list)


# ---------------------------------------------------------------------------
# personal rules save / load
# ---------------------------------------------------------------------------

def test_personal_rules_save_load(tmp_path: Path):
    rules_file = tmp_path / "personal_rules.yaml"

    with patch("stock_master.portfolio.learning.RULES_PATH", rules_file):
        save_personal_rule({"type": "止损", "description": "单票亏损 8% 强制止损"})
        rules = load_personal_rules()

    assert len(rules) == 1
    assert rules[0]["type"] == "止损"
    assert rules[0]["active"] is True
    assert "id" in rules[0]


# ---------------------------------------------------------------------------
# suggest_rules_from_history
# ---------------------------------------------------------------------------

def test_suggest_rules():
    trades = [
        {"code": "600519", "action": "sell", "price": 90, "buy_price": 100, "date": "2026-03-01"},
        {"code": "000858", "action": "sell", "price": 45, "buy_price": 50, "date": "2026-03-10"},
        {"code": "601318", "action": "buy", "price": 60, "date": "2026-03-15"},
    ]
    reviews = [
        {"code": "600519", "date": "2026-03-05", "content": "这次的教训是追高买入"},
    ]

    suggestions = suggest_rules_from_history(trades, reviews)

    assert len(suggestions) >= 1
    types = [s["type"] for s in suggestions]
    assert "止损" in types


# ---------------------------------------------------------------------------
# build_learning_report enhanced
# ---------------------------------------------------------------------------

def test_build_learning_report_enhanced():
    trades = _trades_overtrading()
    reviews = []
    portfolio = _empty_portfolio()

    report = build_learning_report(trades, reviews, portfolio=portfolio)

    assert report["trade_count"] == 5
    assert "behavioral_biases" in report
    assert "trader_profile" in report
    assert report["trader_profile"]["total_trades"] == 5
    assert len(report["bias_flags"]) >= 1
