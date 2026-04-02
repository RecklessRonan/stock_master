"""结构化个股 dossier 构建."""

from __future__ import annotations

from datetime import datetime, timedelta
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
    capital_flow: dict[str, Any] | None = None,
    shareholder_changes: list[dict[str, Any]] | None = None,
    announcements: list[dict[str, Any]] | None = None,
    earnings_forecast: list[dict[str, Any]] | None = None,
    financial_statements: dict[str, Any] | None = None,
    valuation_history: pd.DataFrame | None = None,
) -> EvidenceCoverage:
    sections = {
        "基本信息": bool(info and "error" not in info),
        "行情": not kline.empty,
        "估值": bool(valuation),
        "财务": financial is not None and not financial.empty,
        "新闻": bool(news),
        "宏观": bool(macro),
        "同行对比": bool(peers),
        "资金流向": bool(capital_flow),
        "股东变化": bool(shareholder_changes),
        "公告": bool(announcements),
        "业绩预告": bool(earnings_forecast),
        "完整财报": (
            financial_statements is not None
            and any(v is not None for v in financial_statements.values())
        ),
        "估值历史": valuation_history is not None and not valuation_history.empty,
    }
    available = [name for name, ok in sections.items() if ok]
    missing = [name for name, ok in sections.items() if not ok]
    total = len(sections)
    ratio = len(available) / total if total else 0.0

    stale_sections = _detect_stale(kline=kline, news=news, macro=macro)

    return EvidenceCoverage(
        available_sections=available,
        missing_sections=missing,
        stale_sections=stale_sections,
        coverage_ratio=ratio,
    )


def _detect_stale(
    *,
    kline: pd.DataFrame,
    news: list[dict],
    macro: dict[str, Any],
) -> list[str]:
    """检测数据时效性，返回过时的数据板块名称."""
    stale: list[str] = []
    now = datetime.now()

    if not kline.empty:
        try:
            latest_date = pd.to_datetime(kline.iloc[-1].get("日期", kline.index[-1]))
            if (now - latest_date) > timedelta(days=3):
                stale.append("行情")
        except Exception:
            pass

    if news:
        try:
            latest_news_time = max(
                pd.to_datetime(item["time"])
                for item in news
                if item.get("time")
            )
            if (now - latest_news_time) > timedelta(days=7):
                stale.append("新闻")
        except Exception:
            pass

    if macro:
        headline = macro.get("headline", "")
        current_year = str(now.year)
        if not headline or current_year not in headline:
            stale.append("宏观")

    return stale


def _build_evidence(
    *,
    valuation: dict,
    news: list[dict],
    macro: dict[str, Any],
    capital_flow: dict[str, Any] | None = None,
    shareholder_changes: list[dict[str, Any]] | None = None,
    announcements: list[dict[str, Any]] | None = None,
    earnings_forecast: list[dict[str, Any]] | None = None,
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
                type=EvidenceType.MACRO,
                title="宏观快照",
                content=str(macro),
                source="macro",
                reliability=0.5,
            )
        )
    if capital_flow:
        evidence.append(
            EvidenceItem(
                type=EvidenceType.CAPITAL_FLOW,
                title="资金流向",
                content=str(capital_flow),
                source="akshare",
                reliability=0.7,
            )
        )
    if shareholder_changes:
        evidence.append(
            EvidenceItem(
                type=EvidenceType.SHAREHOLDER,
                title="股东变化",
                content=str(shareholder_changes[:5]),
                source="akshare",
                reliability=0.7,
            )
        )
    if announcements:
        for ann in announcements[:3]:
            evidence.append(
                EvidenceItem(
                    type=EvidenceType.ANNOUNCEMENT,
                    title=ann.get("title", "公告"),
                    content=ann.get("content", ""),
                    source=ann.get("source", "announcement"),
                    reliability=0.8,
                    url=ann.get("url"),
                )
            )
    if earnings_forecast:
        evidence.append(
            EvidenceItem(
                type=EvidenceType.EARNINGS_FORECAST,
                title="业绩预告",
                content=str(earnings_forecast),
                source="akshare",
                reliability=0.7,
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


def generate_teaching_segment(score: ScoreResult, coverage: EvidenceCoverage) -> str:
    """根据评分与覆盖度生成简短教学文字（100-200 字）."""
    parts: list[str] = []

    # 找出得分最高和最低的非 missing 因子
    scored = {
        n: f for n, f in score.factors.items() if f.status != "missing"
    }
    if scored:
        best = max(scored.items(), key=lambda x: x[1].numeric_score())
        worst = min(scored.items(), key=lambda x: x[1].numeric_score())
        parts.append(
            f"本次分析中，{best[0]}维度表现最强（{best[1].numeric_score():.0f}分），"
            f"而{worst[0]}维度相对薄弱（{worst[1].numeric_score():.0f}分）。"
        )

    # 估值分位提示
    val_factor = score.factors.get("估值")
    if val_factor and val_factor.metrics.get("PE历史分位") is not None:
        pct = val_factor.metrics["PE历史分位"]
        if pct < 30:
            parts.append(f"PE 历史分位处于 {pct:.0f}% 低位，说明估值相对便宜。")
        elif pct > 70:
            parts.append(f"PE 历史分位处于 {pct:.0f}% 高位，估值偏贵需谨慎。")

    # 覆盖度提示
    ratio_pct = coverage.coverage_ratio * 100
    parts.append(f"证据覆盖度为 {ratio_pct:.0f}%。")
    if coverage.missing_sections:
        parts.append(f"缺少{'、'.join(coverage.missing_sections[:3])}等数据，建议补齐后再做决策。")
    if coverage.stale_sections:
        parts.append(f"{'、'.join(coverage.stale_sections)}数据时效不足，注意更新。")

    return "".join(parts)


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
    capital_flow: dict[str, Any] | None = None,
    shareholder_changes: list[dict[str, Any]] | None = None,
    announcements: list[dict[str, Any]] | None = None,
    earnings_forecast: list[dict[str, Any]] | None = None,
    financial_statements: dict[str, Any] | None = None,
    valuation_history: pd.DataFrame | None = None,
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
        capital_flow=capital_flow,
        shareholder_changes=shareholder_changes,
        announcements=announcements,
        earnings_forecast=earnings_forecast,
        financial_statements=financial_statements,
        valuation_history=valuation_history,
    )
    return StockDossier(
        code=code,
        stock_name=stock_name or code,
        market=_market_name(code),
        factors=score.factor_details(),
        coverage=coverage,
        evidence=_build_evidence(
            valuation=valuation,
            news=news,
            macro=macro,
            capital_flow=capital_flow,
            shareholder_changes=shareholder_changes,
            announcements=announcements,
            earnings_forecast=earnings_forecast,
        ),
        data_sources=data_sources,
        macro_snapshot=macro,
        peer_benchmark=peers,
        capital_flow=capital_flow or {},
        shareholder_changes=shareholder_changes or [],
        announcements=announcements or [],
        earnings_forecast=earnings_forecast or [],
        financial_statements=financial_statements or {},
        rookie_action=_derive_rookie_action(score, coverage),
        missing_items=coverage.missing_sections,
    )
