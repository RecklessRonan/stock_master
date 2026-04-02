"""事件驱动提醒测试."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from stock_master.portfolio.alerts import (
    Alert,
    AlertSeverity,
    AlertType,
    detect_capital_flow_anomaly,
    detect_valuation_anomaly,
    detect_earnings_alert,
    detect_announcement_alert,
    detect_price_target_alert,
    detect_drawdown_alert,
    scan_all_alerts,
    save_alerts,
    load_alerts,
    acknowledge_alert,
)


# ---------------------------------------------------------------------------
# detect_capital_flow_anomaly
# ---------------------------------------------------------------------------

def test_capital_flow_anomaly_triggers():
    cf = {"main_net_inflow": 8000.0}
    alert = detect_capital_flow_anomaly("600519", cf, threshold=5000)

    assert alert is not None
    assert alert.type == AlertType.CAPITAL_FLOW
    assert alert.severity == AlertSeverity.INFO
    assert "净流入" in alert.title


def test_capital_flow_normal():
    cf = {"main_net_inflow": 2000.0}
    alert = detect_capital_flow_anomaly("600519", cf, threshold=5000)
    assert alert is None


# ---------------------------------------------------------------------------
# detect_valuation_anomaly
# ---------------------------------------------------------------------------

def test_valuation_anomaly_low():
    valuation = {"pe": 8.0, "pb": 0.8}
    alert = detect_valuation_anomaly("600519", valuation, valuation_history_percentile=5.0)

    assert alert is not None
    assert alert.severity == AlertSeverity.INFO
    assert "低位" in alert.title


def test_valuation_anomaly_high():
    valuation = {"pe": 80.0, "pb": 10.0}
    alert = detect_valuation_anomaly("600519", valuation, valuation_history_percentile=95.0)

    assert alert is not None
    assert alert.severity == AlertSeverity.WARNING
    assert "高位" in alert.title


# ---------------------------------------------------------------------------
# detect_earnings_alert
# ---------------------------------------------------------------------------

def test_earnings_positive():
    forecast = [{"type": "预增", "summary": "净利润大幅增长"}]
    alert = detect_earnings_alert("600519", forecast)

    assert alert is not None
    assert alert.severity == AlertSeverity.INFO
    assert "利好" in alert.title


def test_earnings_negative():
    forecast = [{"type": "首亏", "summary": "首次出现亏损"}]
    alert = detect_earnings_alert("600519", forecast)

    assert alert is not None
    assert alert.severity == AlertSeverity.WARNING
    assert "利空" in alert.title


# ---------------------------------------------------------------------------
# detect_announcement_alert
# ---------------------------------------------------------------------------

def test_announcement_buyback():
    announcements = [{"title": "关于回购公司股份的公告"}]
    alert = detect_announcement_alert("600519", announcements)

    assert alert is not None
    assert alert.type == AlertType.ANNOUNCEMENT
    assert "回购" in alert.title


# ---------------------------------------------------------------------------
# detect_price_target_alert
# ---------------------------------------------------------------------------

def test_price_target_reached():
    alert = detect_price_target_alert("600519", current_price=98.0, target_price=100.0)

    assert alert is not None
    assert alert.type == AlertType.PRICE_TARGET
    assert "目标价" in alert.title


# ---------------------------------------------------------------------------
# detect_drawdown_alert
# ---------------------------------------------------------------------------

def test_drawdown_warning():
    pos = {"avg_cost": 100.0, "current_price": 80.0}
    alert = detect_drawdown_alert("600519", pos, max_drawdown_pct=15.0)

    assert alert is not None
    assert alert.type == AlertType.DRAWDOWN
    assert alert.severity == AlertSeverity.WARNING


# ---------------------------------------------------------------------------
# scan_all_alerts
# ---------------------------------------------------------------------------

def test_scan_all_alerts():
    portfolio = {
        "positions": [
            {"code": "600519", "avg_cost": 100, "current_price": 80},
        ],
    }
    watchlist = {
        "stocks": [
            {"code": "000858", "target_price": 55.0},
        ],
    }
    market_data = {
        "600519": {
            "capital_flow": {"main_net_inflow": 10000.0},
            "valuation": {"pe": 8.0, "pb": 0.9},
            "valuation_percentile": 5.0,
            "earnings_forecast": [{"type": "预增", "summary": "增长"}],
            "announcements": [{"title": "关于回购股份的公告"}],
        },
        "000858": {
            "current_price": 53.0,
            "capital_flow": {"main_net_inflow": 200.0},
        },
    }

    alerts = scan_all_alerts(
        portfolio=portfolio,
        watchlist=watchlist,
        market_data=market_data,
    )

    assert isinstance(alerts, list)
    assert len(alerts) >= 2
    types = {a.type for a in alerts}
    assert AlertType.CAPITAL_FLOW in types or AlertType.DRAWDOWN in types


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------

def test_alerts_persistence(tmp_path: Path):
    alerts_file = tmp_path / "alerts.yaml"

    with patch("stock_master.portfolio.alerts.ALERTS_PATH", alerts_file):
        alert1 = Alert(
            type=AlertType.CAPITAL_FLOW,
            severity=AlertSeverity.INFO,
            code="600519",
            title="测试提醒1",
            message="测试消息1",
        )
        alert2 = Alert(
            type=AlertType.DRAWDOWN,
            severity=AlertSeverity.WARNING,
            code="000858",
            title="测试提醒2",
            message="测试消息2",
        )

        save_alerts([alert1, alert2])
        loaded = load_alerts()

    assert len(loaded) == 2
    assert loaded[0]["code"] == "600519"
    assert loaded[1]["code"] == "000858"


def test_acknowledge_alert(tmp_path: Path):
    alerts_file = tmp_path / "alerts.yaml"

    with patch("stock_master.portfolio.alerts.ALERTS_PATH", alerts_file):
        alert = Alert(
            type=AlertType.EARNINGS,
            severity=AlertSeverity.INFO,
            code="600519",
            title="业绩提醒",
            message="预增",
        )
        save_alerts([alert])

        acknowledge_alert(0)

        all_alerts = load_alerts(include_acknowledged=True)
        assert all_alerts[0]["acknowledged"] is True

        unack = load_alerts(include_acknowledged=False)
        assert len(unack) == 0
