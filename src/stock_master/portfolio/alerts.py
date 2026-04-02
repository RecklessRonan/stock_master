"""事件驱动提醒引擎 — 公告/业绩/资金/估值异动检测."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml


# ---------------------------------------------------------------------------
# 类型定义
# ---------------------------------------------------------------------------


class AlertType(str, Enum):
    """提醒类型."""

    ANNOUNCEMENT = "announcement"
    EARNINGS = "earnings"
    CAPITAL_FLOW = "capital_flow"
    VALUATION_ANOMALY = "valuation"
    PRICE_TARGET = "price_target"
    RISK_WARNING = "risk_warning"
    REBALANCE = "rebalance"
    DRAWDOWN = "drawdown"


class AlertSeverity(str, Enum):
    """严重程度."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """单条提醒."""

    type: AlertType
    severity: AlertSeverity
    code: str
    title: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged: bool = False

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "created_at": self.created_at,
            "acknowledged": self.acknowledged,
        }


# ---------------------------------------------------------------------------
# 异动检测函数
# ---------------------------------------------------------------------------

_IMPORTANT_ANNOUNCEMENT_KEYWORDS = [
    "增持", "减持", "回购", "分红", "并购", "重组", "股权激励", "定增",
]


def detect_capital_flow_anomaly(
    code: str,
    capital_flow: dict,
    threshold: float = 5000.0,
) -> Optional[Alert]:
    """检测资金异动 — 主力净流入超过阈值（万元）."""
    net_inflow = capital_flow.get("main_net_inflow", 0.0)
    if abs(net_inflow) < threshold:
        return None

    if net_inflow > 0:
        severity = AlertSeverity.INFO
        title = f"{code} 主力大额净流入"
        message = f"主力净流入 {net_inflow:.0f} 万元，超出阈值 {threshold:.0f} 万元。"
    else:
        severity = AlertSeverity.WARNING
        title = f"{code} 主力大额净流出"
        message = f"主力净流出 {abs(net_inflow):.0f} 万元，超出阈值 {threshold:.0f} 万元。"

    return Alert(
        type=AlertType.CAPITAL_FLOW,
        severity=severity,
        code=code,
        title=title,
        message=message,
        data={"main_net_inflow": net_inflow, "threshold": threshold},
    )


def detect_valuation_anomaly(
    code: str,
    valuation: dict,
    valuation_history_percentile: float | None,
) -> Optional[Alert]:
    """检测估值异动 — PE/PB 历史分位数过低或过高."""
    if valuation_history_percentile is None:
        return None

    pe = valuation.get("pe")
    pb = valuation.get("pb")
    label_parts: list[str] = []
    if pe is not None:
        label_parts.append(f"PE={pe:.1f}")
    if pb is not None:
        label_parts.append(f"PB={pb:.2f}")
    label = ", ".join(label_parts) if label_parts else "估值数据"

    if valuation_history_percentile <= 10.0:
        return Alert(
            type=AlertType.VALUATION_ANOMALY,
            severity=AlertSeverity.INFO,
            code=code,
            title=f"{code} 估值处于历史低位",
            message=f"当前 {label}，历史分位数 {valuation_history_percentile:.1f}%，处于极低水平。",
            data={"valuation": valuation, "percentile": valuation_history_percentile},
        )

    if valuation_history_percentile >= 90.0:
        return Alert(
            type=AlertType.VALUATION_ANOMALY,
            severity=AlertSeverity.WARNING,
            code=code,
            title=f"{code} 估值处于历史高位",
            message=f"当前 {label}，历史分位数 {valuation_history_percentile:.1f}%，处于极高水平。",
            data={"valuation": valuation, "percentile": valuation_history_percentile},
        )

    return None


def detect_earnings_alert(
    code: str,
    earnings_forecast: list[dict],
) -> Optional[Alert]:
    """检测业绩预告 — 预增/预减/扭亏/首亏."""
    if not earnings_forecast:
        return None

    latest = earnings_forecast[0]
    forecast_type = latest.get("type", "")
    positive_types = {"预增", "扭亏", "略增", "续盈"}
    negative_types = {"预减", "首亏", "略减", "续亏"}

    if forecast_type in positive_types:
        return Alert(
            type=AlertType.EARNINGS,
            severity=AlertSeverity.INFO,
            code=code,
            title=f"{code} 业绩预告利好：{forecast_type}",
            message=f"最新业绩预告类型为「{forecast_type}」，{latest.get('summary', '')}",
            data={"forecast": latest},
        )

    if forecast_type in negative_types:
        return Alert(
            type=AlertType.EARNINGS,
            severity=AlertSeverity.WARNING,
            code=code,
            title=f"{code} 业绩预告利空：{forecast_type}",
            message=f"最新业绩预告类型为「{forecast_type}」，{latest.get('summary', '')}",
            data={"forecast": latest},
        )

    return None


def detect_announcement_alert(
    code: str,
    announcements: list[dict],
) -> Optional[Alert]:
    """检测重要公告 — 增持/减持/回购/分红等关键词."""
    if not announcements:
        return None

    for ann in announcements:
        title_text = ann.get("title", "")
        matched = [kw for kw in _IMPORTANT_ANNOUNCEMENT_KEYWORDS if kw in title_text]
        if not matched:
            continue

        negative_keywords = {"减持"}
        is_negative = bool(negative_keywords & set(matched))
        severity = AlertSeverity.WARNING if is_negative else AlertSeverity.INFO

        return Alert(
            type=AlertType.ANNOUNCEMENT,
            severity=severity,
            code=code,
            title=f"{code} 重要公告：{'、'.join(matched)}",
            message=f"公告标题：{title_text}",
            data={"announcement": ann, "matched_keywords": matched},
        )

    return None


def detect_price_target_alert(
    code: str,
    current_price: float,
    target_price: float,
) -> Optional[Alert]:
    """检测是否触达目标价."""
    if current_price > target_price:
        return None

    gap_pct = (target_price - current_price) / target_price * 100
    if gap_pct > 5.0:
        return None

    return Alert(
        type=AlertType.PRICE_TARGET,
        severity=AlertSeverity.INFO,
        code=code,
        title=f"{code} 接近目标价",
        message=(
            f"当前价 {current_price:.2f}，目标价 {target_price:.2f}，"
            f"差距 {gap_pct:.1f}%。"
        ),
        data={
            "current_price": current_price,
            "target_price": target_price,
            "gap_pct": round(gap_pct, 2),
        },
    )


def detect_drawdown_alert(
    code: str,
    position: dict,
    max_drawdown_pct: float = 15.0,
) -> Optional[Alert]:
    """检测单票回撤预警."""
    cost = position.get("avg_cost")
    current = position.get("current_price")
    if cost is None or current is None or cost <= 0:
        return None

    drawdown = (cost - current) / cost * 100
    if drawdown < max_drawdown_pct:
        return None

    severity = AlertSeverity.CRITICAL if drawdown >= 25.0 else AlertSeverity.WARNING
    return Alert(
        type=AlertType.DRAWDOWN,
        severity=severity,
        code=code,
        title=f"{code} 回撤预警",
        message=(
            f"当前回撤 {drawdown:.1f}%（成本 {cost:.2f} → 现价 {current:.2f}），"
            f"超过阈值 {max_drawdown_pct:.1f}%。"
        ),
        data={
            "avg_cost": cost,
            "current_price": current,
            "drawdown_pct": round(drawdown, 2),
            "threshold_pct": max_drawdown_pct,
        },
    )


# ---------------------------------------------------------------------------
# 批量扫描
# ---------------------------------------------------------------------------


def scan_all_alerts(
    *,
    portfolio: dict,
    watchlist: dict,
    market_data: dict[str, dict],
) -> list[Alert]:
    """批量扫描所有持仓和观察清单，生成提醒列表."""
    alerts: list[Alert] = []

    # --- 持仓扫描 ---
    for pos in portfolio.get("positions", []):
        code = pos.get("code", "")
        data = market_data.get(code, {})

        if cf := data.get("capital_flow"):
            if alert := detect_capital_flow_anomaly(code, cf):
                alerts.append(alert)

        if val := data.get("valuation"):
            pct = data.get("valuation_percentile")
            if alert := detect_valuation_anomaly(code, val, pct):
                alerts.append(alert)

        if ef := data.get("earnings_forecast"):
            if alert := detect_earnings_alert(code, ef):
                alerts.append(alert)

        if anns := data.get("announcements"):
            if alert := detect_announcement_alert(code, anns):
                alerts.append(alert)

        if alert := detect_drawdown_alert(code, pos):
            alerts.append(alert)

    # --- 观察清单扫描 ---
    for stock in watchlist.get("stocks", []):
        code = stock.get("code", "")
        data = market_data.get(code, {})
        current_price = data.get("current_price")
        target_price = stock.get("target_price")

        if current_price is not None and target_price is not None:
            if alert := detect_price_target_alert(code, current_price, target_price):
                alerts.append(alert)

        if cf := data.get("capital_flow"):
            if alert := detect_capital_flow_anomaly(code, cf):
                alerts.append(alert)

        if val := data.get("valuation"):
            pct = data.get("valuation_percentile")
            if alert := detect_valuation_anomaly(code, val, pct):
                alerts.append(alert)

        if ef := data.get("earnings_forecast"):
            if alert := detect_earnings_alert(code, ef):
                alerts.append(alert)

        if anns := data.get("announcements"):
            if alert := detect_announcement_alert(code, anns):
                alerts.append(alert)

    return alerts


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------

ALERTS_PATH = Path("journal/alerts.yaml")


def save_alerts(alerts: list[Alert]) -> None:
    """保存提醒到文件（追加模式，不覆盖已有记录）."""
    existing: list[dict] = []
    if ALERTS_PATH.exists():
        raw = yaml.safe_load(ALERTS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            existing = raw

    existing.extend(a.to_dict() for a in alerts)
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALERTS_PATH.write_text(
        yaml.dump(existing, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def load_alerts(include_acknowledged: bool = False) -> list[dict]:
    """加载提醒列表."""
    if not ALERTS_PATH.exists():
        return []

    raw = yaml.safe_load(ALERTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []

    if include_acknowledged:
        return raw
    return [a for a in raw if not a.get("acknowledged", False)]


def acknowledge_alert(index: int) -> None:
    """确认（静默）指定提醒."""
    all_alerts = load_alerts(include_acknowledged=True)
    if 0 <= index < len(all_alerts):
        all_alerts[index]["acknowledged"] = True
        ALERTS_PATH.write_text(
            yaml.dump(all_alerts, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def format_alerts_summary(alerts: list[Alert]) -> str:
    """格式化提醒摘要为可读文本."""
    if not alerts:
        return "当前无提醒。"

    severity_icon = {
        AlertSeverity.INFO: "ℹ️",
        AlertSeverity.WARNING: "⚠️",
        AlertSeverity.CRITICAL: "🚨",
    }

    lines: list[str] = [f"共 {len(alerts)} 条提醒：", ""]
    for i, a in enumerate(alerts, 1):
        icon = severity_icon.get(a.severity, "•")
        lines.append(f"{i}. {icon} [{a.severity.value.upper()}] {a.title}")
        lines.append(f"   {a.message}")
        lines.append("")

    return "\n".join(lines)
