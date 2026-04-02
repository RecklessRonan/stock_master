"""结构化个股 dossier 构建."""

from __future__ import annotations

from typing import Any

import pandas as pd

from stock_master.analysis.quantitative import ScoreResult
from stock_master.models.research import (
    EvidenceCoverage,
    EvidenceItem,
    EvidenceType,
    RookieAction,
    StockDossier,
)


def _market_name(code: str) -> str:
    return "港股" if code.isdigit() and len(code) <= 5 else "A股"


def _build_coverage(
    *,
    info: dict,
    kline: pd.DataFrame,
    valuation: dict,
    financial: pd.DataFrame | None,
    news: list[dict],
    macro: dict[str, Any],
    peers: list[dict[str, Any]],
) -> EvidenceCoverage:
    sections = {
        "基本信息": bool(info and "error" not in info),
        "行情": not kline.empty,
        "估值": bool(valuation),
        "财务": financial is not None and not financial.empty,
        "新闻": bool(news),
        "宏观": bool(macro),
        "同行对比": bool(peers),
    }
    available = [name for name, ok in sections.items() if ok]
    missing = [name for name, ok in sections.items() if not ok]
    total = len(sections)
    ratio = len(available) / total if total else 0.0
    return EvidenceCoverage(
        available_sections=available,
        missing_sections=missing,
        coverage_ratio=ratio,
    )


def _build_evidence(
    *,
    valuation: dict,
    news: list[dict],
    macro: dict[str, Any],
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    if valuation:
        evidence.append(
            EvidenceItem(
                type=EvidenceType.MARKET_DATA,
                title="估值快照",
                content=str(valuation),
                source="akshare",
                reliability=0.8,
            )
        )
    for item in news[:5]:
        evidence.append(
            EvidenceItem(
                type=EvidenceType.NEWS,
                title=item.get("title", "近期新闻"),
                content=item.get("content", ""),
                source=item.get("source", "news"),
                reliability=0.6,
                url=item.get("url"),
            )
        )
    if macro:
        evidence.append(
            EvidenceItem(
                type=EvidenceType.OTHER,
                title="宏观快照",
                content=str(macro),
                source="macro",
                reliability=0.5,
            )
        )
    return evidence


def _derive_rookie_action(score: ScoreResult, coverage: EvidenceCoverage) -> RookieAction:
    overall = score.overall
    confidence = score.confidence
    quality = score.factors["质量"].numeric_score()
    risk = score.factors["风险"].numeric_score()
    value = score.factors["估值"].numeric_score()
    critical_missing = any(
        score.factors[name].status == "missing" for name in ("趋势", "风险", "催化剂")
    )

    verdict = "观察"
    max_position = 0.0
    hold_period = "等待更多证据"
    if confidence < 60 or critical_missing:
        verdict = "先补证据"
    elif overall >= 75 and quality >= 70 and risk >= 60:
        verdict = "可小仓分批"
        max_position = 10.0 if value >= 55 else 8.0
        hold_period = "中期跟踪"
    elif overall >= 65:
        verdict = "观察买点"
        max_position = 6.0
        hold_period = "等待回调或催化确认"
    else:
        verdict = "暂时回避"
        hold_period = "等待基本面或风险改善"

    warnings = []
    if coverage.missing_sections:
        warnings.append(f"证据缺口：{', '.join(coverage.missing_sections)}")
    if score.factors["风险"].score is not None and score.factors["风险"].numeric_score() < 50:
        warnings.append("风险分偏低，优先控制仓位。")
    if score.factors["催化剂"].score is not None and score.factors["催化剂"].numeric_score() < 45:
        warnings.append("近期催化剂不足或偏负面。")

    checklist = [
        "确认买入逻辑和失效条件是否写清楚",
        "单票仓位不要超过风险预算",
        "先看是否与现有持仓高度同质",
        "若缺关键证据，先观察而不是冲动下单",
    ]

    return RookieAction(
        verdict=verdict,
        max_position_pct=max_position,
        preferred_holding_period=hold_period,
        checklist=checklist,
        warnings=warnings,
    )


def build_stock_dossier(
    *,
    code: str,
    stock_name: str,
    score: ScoreResult,
    info: dict,
    kline: pd.DataFrame,
    valuation: dict,
    financial: pd.DataFrame | None,
    news: list[dict],
    macro: dict[str, Any] | None = None,
    peers: list[dict[str, Any]] | None = None,
    data_sources: dict[str, list[str]] | None = None,
) -> StockDossier:
    macro = macro or {}
    peers = peers or []
    data_sources = data_sources or {}
    coverage = _build_coverage(
        info=info,
        kline=kline,
        valuation=valuation,
        financial=financial,
        news=news,
        macro=macro,
        peers=peers,
    )
    return StockDossier(
        code=code,
        stock_name=stock_name or code,
        market=_market_name(code),
        factors=score.factor_details(),
        coverage=coverage,
        evidence=_build_evidence(valuation=valuation, news=news, macro=macro),
        data_sources=data_sources,
        macro_snapshot=macro,
        peer_benchmark=peers,
        rookie_action=_derive_rookie_action(score, coverage),
        missing_items=coverage.missing_sections,
    )
