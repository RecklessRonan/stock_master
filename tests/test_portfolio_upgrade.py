"""组合风控、自选和学习飞轮测试."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from stock_master.portfolio.guardrails import analyze_portfolio_guardrails, evaluate_buy_candidate
from stock_master.portfolio.learning import build_learning_report
from stock_master.portfolio.reviewer import create_review_template
from stock_master.portfolio.watchlist import generate_watchlist_alerts, upsert_watchlist_item


def test_analyze_portfolio_guardrails_flags_concentration():
    portfolio = {
        "positions": [
            {"code": "600000", "name": "银行A", "shares": 8000, "avg_cost": 10.0, "current_price": 10.0},
            {"code": "000001", "name": "平安A", "shares": 1000, "avg_cost": 10.0, "current_price": 10.0},
        ]
    }

    result = analyze_portfolio_guardrails(portfolio)

    assert result["position_count"] == 2
    assert result["max_single_position_pct"] > 80
    assert result["warnings"]


def test_evaluate_buy_candidate_applies_position_limits():
    portfolio = {
        "positions": [
            {"code": "600000", "name": "银行A", "shares": 3000, "avg_cost": 10.0, "current_price": 10.0},
            {"code": "000001", "name": "平安A", "shares": 3000, "avg_cost": 10.0, "current_price": 10.0},
        ]
    }
    candidate = {"code": "300750", "name": "宁德时代", "planned_position_pct": 18.0}

    result = evaluate_buy_candidate(portfolio, candidate)

    assert result["verdict"] == "谨慎"
    assert any("单票" in warning for warning in result["warnings"])


def test_watchlist_upsert_and_alert_generation():
    watchlist = {"updated_at": "2026-04-02", "stocks": []}
    updated = upsert_watchlist_item(
        watchlist,
        code="002273",
        name="水晶光电",
        bucket="wait_price",
        target_price=18.5,
        thesis="等待回调后再看",
    )

    alerts = generate_watchlist_alerts(
        updated,
        dossiers={"002273": {"rookie_action": {"verdict": "观察买点"}}},
        market_prices={"002273": 18.2},
    )

    assert updated["stocks"][0]["bucket"] == "wait_price"
    assert alerts
    assert alerts[0]["type"] == "opportunity"


def test_build_learning_report_flags_overtrading_and_missing_reviews():
    trades = [
        {"code": "002273", "confidence": 4, "review_date": "", "tags": []},
        {"code": "300750", "confidence": 5, "review_date": "", "tags": []},
        {"code": "600036", "confidence": 3, "review_date": "", "tags": []},
        {"code": "000001", "confidence": 4, "review_date": "", "tags": []},
    ]
    reviews = []

    report = build_learning_report(trades, reviews)

    assert report["bias_flags"]
    assert any("复盘" in flag for flag in report["bias_flags"])
    assert any("交易" in flag for flag in report["bias_flags"])


def test_create_review_template_preserves_existing_weekly_file(tmp_path: Path):
    with patch("stock_master.portfolio.reviewer.REVIEWS_DIR", tmp_path):
        path = create_review_template(code="", review_type="weekly")
        path.write_text("# 已填写内容\n\n不要覆盖我。\n", encoding="utf-8")
        second = create_review_template(code="", review_type="weekly")

    assert second == path
    assert "不要覆盖我" in path.read_text(encoding="utf-8")
