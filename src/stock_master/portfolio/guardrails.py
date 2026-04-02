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


def _total_assets(portfolio: dict) -> float:
    positions = portfolio.get("positions", [])
    pos_value = sum(_position_value(p) for p in positions)
    cash = float(portfolio.get("cash", 0) or 0)
    return pos_value + cash


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


# ---------------------------------------------------------------------------
# 2a. 行业集中度检查
# ---------------------------------------------------------------------------

def check_industry_concentration(
    portfolio: dict,
    *,
    max_industry_pct: float = 40.0,
) -> dict:
    """检查行业集中度，按 industry 字段分组."""
    positions = portfolio.get("positions", [])
    total = _total_assets(portfolio) or 1.0

    industry_values: dict[str, float] = {}
    for pos in positions:
        industry = pos.get("industry", "未知")
        industry_values[industry] = industry_values.get(industry, 0.0) + _position_value(pos)

    concentrations = {k: round(v / total * 100, 1) for k, v in industry_values.items()}

    warnings: list[str] = []
    for ind, pct in concentrations.items():
        if pct > max_industry_pct:
            warnings.append(f"行业 [{ind}] 集中度 {pct:.1f}% 超过阈值 {max_industry_pct:.1f}%。")

    max_pct = max(concentrations.values()) if concentrations else 0.0
    return {
        "industry_concentrations": concentrations,
        "warnings": warnings,
        "max_industry_pct": round(max_pct, 1),
    }


# ---------------------------------------------------------------------------
# 2b. 回撤阈值检查
# ---------------------------------------------------------------------------

def check_drawdown(
    portfolio: dict,
    *,
    max_drawdown_pct: float = 15.0,
) -> dict:
    """计算每只持仓浮亏及组合级回撤."""
    positions = portfolio.get("positions", [])
    total = _total_assets(portfolio) or 1.0

    position_drawdowns: dict[str, float] = {}
    portfolio_drawdown = 0.0

    for pos in positions:
        avg_cost = float(pos.get("avg_cost", 0) or 0)
        current_price = float(pos.get("current_price", avg_cost) or avg_cost)
        if avg_cost > 0:
            pnl_pct = (current_price - avg_cost) / avg_cost * 100
        else:
            pnl_pct = 0.0

        code = pos.get("code", "unknown")
        position_drawdowns[code] = round(pnl_pct, 2)

        if pnl_pct < 0:
            weight = _position_value(pos) / total
            portfolio_drawdown += pnl_pct * weight

    portfolio_drawdown = round(portfolio_drawdown, 2)
    warnings: list[str] = []

    for code, dd in position_drawdowns.items():
        if dd < -max_drawdown_pct:
            warnings.append(f"{code} 浮亏 {dd:.1f}% 超过阈值 -{max_drawdown_pct:.1f}%。")
    if portfolio_drawdown < -max_drawdown_pct:
        warnings.append(f"组合加权回撤 {portfolio_drawdown:.1f}% 超过阈值 -{max_drawdown_pct:.1f}%。")

    return {
        "position_drawdowns": position_drawdowns,
        "portfolio_drawdown": portfolio_drawdown,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 2c. 现金比例检查
# ---------------------------------------------------------------------------

def check_cash_ratio(
    portfolio: dict,
    *,
    min_cash_pct: float = 20.0,
) -> dict:
    """检查现金占总资产比例."""
    cash = float(portfolio.get("cash", 0) or 0)
    total = _total_assets(portfolio) or 1.0
    cash_pct = round(cash / total * 100, 1)

    warnings: list[str] = []
    if cash_pct < min_cash_pct:
        warnings.append(f"现金占比 {cash_pct:.1f}% 低于最低要求 {min_cash_pct:.1f}%。")

    return {"cash_pct": cash_pct, "warnings": warnings}


# ---------------------------------------------------------------------------
# 2d. 再平衡建议
# ---------------------------------------------------------------------------

def suggest_rebalance(
    portfolio: dict,
    *,
    max_deviation_pct: float = 10.0,
) -> dict:
    """比较实际仓位与目标仓位，超过偏离阈值则建议再平衡."""
    positions = portfolio.get("positions", [])
    total = _total_assets(portfolio) or 1.0

    deviations: list[dict] = []
    for pos in positions:
        target = float(pos.get("target_pct", 0) or 0)
        if target <= 0:
            continue
        actual = _position_value(pos) / total * 100
        dev = round(actual - target, 2)
        if abs(dev) > max_deviation_pct:
            direction = "超配" if dev > 0 else "低配"
            deviations.append({
                "code": pos.get("code", ""),
                "name": pos.get("name", ""),
                "target_pct": target,
                "actual_pct": round(actual, 1),
                "deviation_pct": dev,
                "direction": direction,
            })

    return {
        "deviations": deviations,
        "needs_rebalance": len(deviations) > 0,
    }


# ---------------------------------------------------------------------------
# 2e. 追涨检测
# ---------------------------------------------------------------------------

def check_chasing_high(
    code: str,
    kline_data: dict,
) -> dict:
    """检测是否追涨：当前价接近近期高点或短期涨幅过大."""
    recent_high = float(kline_data.get("recent_high", 0) or 0)
    current_price = float(kline_data.get("current_price", 0) or 0)
    pct_from_high = float(kline_data.get("pct_from_high", 0) or 0)

    warnings: list[str] = []

    if recent_high > 0 and current_price > 0:
        ratio = current_price / recent_high
        if ratio > 0.95:
            warnings.append(f"{code} 当前价格接近近期高点（{ratio:.1%}），有追涨风险。")

    if pct_from_high > 15:
        warnings.append(f"{code} 短期涨幅 {pct_from_high:.1f}% 过大，追高风险较高。")

    return {
        "code": code,
        "current_price": current_price,
        "recent_high": recent_high,
        "pct_from_high": pct_from_high,
        "is_chasing": len(warnings) > 0,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 2f. 同质检测
# ---------------------------------------------------------------------------

def check_homogeneity(
    portfolio: dict,
    candidate_code: str,
    candidate_info: dict,
) -> dict:
    """检查候选股与现有持仓是否同行业、同概念."""
    positions = portfolio.get("positions", [])
    cand_industry = candidate_info.get("industry", "")
    cand_concepts = set(candidate_info.get("concepts", []))

    warnings: list[str] = []
    overlap_positions: list[str] = []

    for pos in positions:
        if pos.get("code") == candidate_code:
            continue
        pos_industry = pos.get("industry", "")
        pos_concepts = set(pos.get("concepts", []))

        if cand_industry and pos_industry and cand_industry == pos_industry:
            overlap_positions.append(pos.get("code", ""))
            warnings.append(
                f"{candidate_code} 与持仓 {pos.get('code', '')} 同属 [{cand_industry}] 行业。"
            )

        common = cand_concepts & pos_concepts
        if common:
            warnings.append(
                f"{candidate_code} 与持仓 {pos.get('code', '')} 共享概念：{', '.join(common)}。"
            )

    return {
        "candidate_code": candidate_code,
        "overlap_positions": overlap_positions,
        "is_homogeneous": len(warnings) > 0,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 2g. 增强 evaluate_buy_candidate
# ---------------------------------------------------------------------------

def evaluate_buy_candidate(
    portfolio: dict,
    candidate: dict,
    *,
    max_single_position_pct: float = 12.0,
    kline_data: dict | None = None,
    dossier: dict | None = None,
    candidate_info: dict | None = None,
) -> dict:
    """评估单个候选标的是否适合买入（增强版）."""
    warnings: list[str] = []
    planned_position_pct = float(candidate.get("planned_position_pct") or 0.0)

    if planned_position_pct > max_single_position_pct:
        warnings.append(
            f"单票计划仓位过高（{planned_position_pct:.1f}% > {max_single_position_pct:.1f}%）。"
        )

    portfolio_risk = analyze_portfolio_guardrails(portfolio)
    warnings.extend(portfolio_risk["warnings"])

    code = candidate.get("code", "")

    # 追涨检测
    chasing_result: dict | None = None
    if kline_data is not None:
        chasing_result = check_chasing_high(code, kline_data)
        warnings.extend(chasing_result["warnings"])

    # 同质检测
    homogeneity_result: dict | None = None
    if candidate_info is not None:
        homogeneity_result = check_homogeneity(portfolio, code, candidate_info)
        warnings.extend(homogeneity_result["warnings"])

    # 证据完整性检查
    evidence_warnings: list[str] = []
    if dossier is not None:
        sections = dossier.get("sections", {})
        required = ["research", "valuation", "risk"]
        for sec in required:
            if sec not in sections or not sections[sec]:
                evidence_warnings.append(f"Dossier 中缺少 [{sec}] 证据，决策依据不完整。")
        warnings.extend(evidence_warnings)
    else:
        warnings.append("未提供 Dossier，缺少系统化研究证据。")

    # 失效条件检查
    invalidation_warnings: list[str] = []
    if dossier is not None:
        inv = dossier.get("invalidation_conditions", [])
        triggered = [c for c in inv if c.get("triggered")]
        for c in triggered:
            invalidation_warnings.append(f"失效条件已触发：{c.get('description', '未知条件')}")
        warnings.extend(invalidation_warnings)

    verdict = "可观察"
    if warnings:
        verdict = "谨慎"

    return {
        "code": code,
        "name": candidate.get("name", ""),
        "planned_position_pct": planned_position_pct,
        "verdict": verdict,
        "warnings": warnings,
        "portfolio_guardrails": portfolio_risk,
        "chasing_check": chasing_result,
        "homogeneity_check": homogeneity_result,
    }


# ---------------------------------------------------------------------------
# 2h. 综合风控分析
# ---------------------------------------------------------------------------

def comprehensive_portfolio_analysis(portfolio: dict) -> dict:
    """调用所有风控检查，返回综合报告."""
    guardrails = analyze_portfolio_guardrails(portfolio)
    industry = check_industry_concentration(portfolio)
    drawdown = check_drawdown(portfolio)
    cash = check_cash_ratio(portfolio)
    rebalance = suggest_rebalance(portfolio)

    all_warnings: list[str] = []
    all_warnings.extend(guardrails["warnings"])
    all_warnings.extend(industry["warnings"])
    all_warnings.extend(drawdown["warnings"])
    all_warnings.extend(cash["warnings"])

    risk_level = "低"
    if len(all_warnings) >= 3:
        risk_level = "高"
    elif len(all_warnings) >= 1:
        risk_level = "中"

    return {
        "risk_level": risk_level,
        "total_warnings": len(all_warnings),
        "all_warnings": all_warnings,
        "guardrails": guardrails,
        "industry_concentration": industry,
        "drawdown": drawdown,
        "cash_ratio": cash,
        "rebalance": rebalance,
    }
