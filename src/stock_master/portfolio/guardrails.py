"""组合风控与买前检查."""

from __future__ import annotations


def _position_value(position: dict) -> float:
    if position.get("market_value") is not None:
        try:
            return float(position["market_value"])
        except (TypeError, ValueError):
            pass
    shares = float(position.get("shares", 0) or 0)
    price = float(position.get("current_price") or position.get("avg_cost") or 0)
    return shares * price


def analyze_portfolio_guardrails(
    portfolio: dict,
    *,
    max_single_position_pct: float = 25.0,
    min_positions: int = 3,
) -> dict:
    """分析当前组合的集中度和分散度."""
    positions = portfolio.get("positions", [])
    position_values = [_position_value(pos) for pos in positions]
    total_value = sum(position_values)
    position_count = len(positions)
    max_single_pct = 0.0
    if total_value > 0 and position_values:
        max_single_pct = max(position_values) / total_value * 100

    warnings: list[str] = []
    if position_count and max_single_pct > max_single_position_pct:
        warnings.append(f"单票集中度过高（{max_single_pct:.1f}% > {max_single_position_pct:.1f}%）。")
    if 0 < position_count < min_positions:
        warnings.append(f"当前仅有 {position_count} 个持仓，分散度不足。")

    verdict = "稳健"
    if warnings:
        verdict = "谨慎"

    return {
        "position_count": position_count,
        "total_market_value": round(total_value, 2),
        "max_single_position_pct": round(max_single_pct, 1),
        "warnings": warnings,
        "verdict": verdict,
    }


def evaluate_buy_candidate(
    portfolio: dict,
    candidate: dict,
    *,
    max_single_position_pct: float = 12.0,
) -> dict:
    """评估单个候选标的是否适合买入."""
    warnings: list[str] = []
    planned_position_pct = float(candidate.get("planned_position_pct") or 0.0)

    if planned_position_pct > max_single_position_pct:
        warnings.append(
            f"单票计划仓位过高（{planned_position_pct:.1f}% > {max_single_position_pct:.1f}%）。"
        )

    portfolio_risk = analyze_portfolio_guardrails(portfolio)
    warnings.extend(portfolio_risk["warnings"])

    verdict = "可观察"
    if warnings:
        verdict = "谨慎"

    return {
        "code": candidate.get("code", ""),
        "name": candidate.get("name", ""),
        "planned_position_pct": planned_position_pct,
        "verdict": verdict,
        "warnings": warnings,
        "portfolio_guardrails": portfolio_risk,
    }
