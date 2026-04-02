"""模拟盘测试."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from stock_master.portfolio.execution import PaperPortfolio, ExecutionAdapter, ExecutionMode


# ---------------------------------------------------------------------------
# PaperPortfolio
# ---------------------------------------------------------------------------

def test_paper_portfolio_buy(tmp_path: Path):
    paper_file = tmp_path / "paper_portfolio.yaml"

    with patch.object(PaperPortfolio, "PAPER_PATH", paper_file):
        pp = PaperPortfolio()
        result = pp.execute_trade(
            code="600519",
            name="贵州茅台",
            action="buy",
            price=1800.0,
            shares=100,
            reason="低估买入",
        )

    assert result["status"] == "paper_executed"
    assert result["trade"]["code"] == "600519"
    assert result["trade"]["shares"] == 100
    assert pp.data["cash"] == 1_000_000 - 1800 * 100

    positions = pp.get_positions()
    assert len(positions) == 1
    assert positions[0]["code"] == "600519"
    assert positions[0]["avg_cost"] == 1800.0


def test_paper_portfolio_sell(tmp_path: Path):
    paper_file = tmp_path / "paper_portfolio.yaml"

    with patch.object(PaperPortfolio, "PAPER_PATH", paper_file):
        pp = PaperPortfolio()
        pp.execute_trade("600519", "贵州茅台", "buy", 1800.0, 100)

        result = pp.execute_trade(
            code="600519",
            name="贵州茅台",
            action="sell",
            price=2000.0,
            shares=50,
        )

    assert result["status"] == "paper_executed"
    positions = pp.get_positions()
    assert len(positions) == 1
    assert positions[0]["shares"] == 50


def test_paper_portfolio_performance(tmp_path: Path):
    paper_file = tmp_path / "paper_portfolio.yaml"

    with patch.object(PaperPortfolio, "PAPER_PATH", paper_file):
        pp = PaperPortfolio()
        pp.execute_trade("600519", "贵州茅台", "buy", 100.0, 1000)

        pp.data["positions"][0]["current_price"] = 110.0
        perf = pp.get_performance()

    assert perf["initial_cash"] == 1_000_000.0
    assert perf["position_value"] == 110.0 * 1000
    assert perf["total_pnl"] > 0
    assert perf["total_return_pct"] > 0
    assert perf["trade_count"] == 1

    detail = perf["position_details"][0]
    assert detail["pnl"] == (110.0 - 100.0) * 1000
    assert detail["pnl_pct"] == 10.0


# ---------------------------------------------------------------------------
# ExecutionAdapter
# ---------------------------------------------------------------------------

def test_execution_adapter_paper(tmp_path: Path):
    paper_file = tmp_path / "paper_portfolio.yaml"

    with patch.object(PaperPortfolio, "PAPER_PATH", paper_file):
        adapter = ExecutionAdapter(mode=ExecutionMode.PAPER)
        result = adapter.execute(
            code="600519",
            name="贵州茅台",
            action="buy",
            price=1800.0,
            shares=10,
            reason="测试",
        )

    assert result["status"] == "paper_executed"
    assert "模拟交易已执行" in result["message"]
