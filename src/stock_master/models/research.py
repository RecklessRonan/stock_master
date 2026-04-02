"""研究流程与结构化 dossier 领域对象."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    MARKET_DATA = "market_data"
    FINANCIAL = "financial"
    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    KLINE_IMAGE = "kline_image"
    ANALYST_REPORT = "analyst_report"
    CAPITAL_FLOW = "capital_flow"
    SHAREHOLDER = "shareholder"
    EARNINGS_FORECAST = "earnings_forecast"
    FINANCIAL_STATEMENT = "financial_statement"
    PEER_COMPARISON = "peer_comparison"
    MACRO = "macro"
    OTHER = "other"


class EvidenceItem(BaseModel):
    """原始事实/证据，附带来源与可信度."""

    type: EvidenceType
    title: str
    content: str
    source: str
    fetched_at: datetime = Field(default_factory=datetime.now)
    reliability: float = Field(default=0.8, ge=0.0, le=1.0)
    url: Optional[str] = None


class EvidenceCoverage(BaseModel):
    """证据覆盖度摘要."""

    available_sections: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    stale_sections: list[str] = Field(default_factory=list)
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class RookieAction(BaseModel):
    """面向新手的行动建议."""

    verdict: str = "观察"
    max_position_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    preferred_holding_period: str = ""
    checklist: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    """多源数据证据包 — 标准化证据容器."""

    code: str
    stock_name: str = ""
    collected_at: datetime = Field(default_factory=datetime.now)
    items: list[EvidenceItem] = Field(default_factory=list)
    capital_flow: dict[str, Any] = Field(default_factory=dict)
    shareholder_changes: list[dict[str, Any]] = Field(default_factory=list)
    announcements: list[dict[str, Any]] = Field(default_factory=list)
    earnings_forecast: list[dict[str, Any]] = Field(default_factory=list)
    financial_statements: dict[str, Any] = Field(default_factory=dict)
    valuation_history: dict[str, Any] = Field(default_factory=dict)
    peer_comparison: list[dict[str, Any]] = Field(default_factory=list)
    macro_snapshot: dict[str, Any] = Field(default_factory=dict)
    data_sources: dict[str, list[str]] = Field(default_factory=dict)


class StockDossier(BaseModel):
    """个股研究事实包."""

    code: str
    stock_name: str = ""
    market: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)
    factors: dict[str, dict[str, Any]] = Field(default_factory=dict)
    coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    data_sources: dict[str, list[str]] = Field(default_factory=dict)
    macro_snapshot: dict[str, Any] = Field(default_factory=dict)
    peer_benchmark: list[dict[str, Any]] = Field(default_factory=list)
    capital_flow: dict[str, Any] = Field(default_factory=dict)
    shareholder_changes: list[dict[str, Any]] = Field(default_factory=list)
    announcements: list[dict[str, Any]] = Field(default_factory=list)
    earnings_forecast: list[dict[str, Any]] = Field(default_factory=list)
    financial_statements: dict[str, Any] = Field(default_factory=dict)
    evidence_pack: Optional["EvidencePack"] = None
    rookie_action: RookieAction = Field(default_factory=RookieAction)
    missing_items: list[str] = Field(default_factory=list)


class ResearchMemo(BaseModel):
    """单维度研究报告（基本面/技术面/风险/行业等）."""

    dimension: str
    model_name: str
    summary: str
    bullish_points: list[str] = Field(default_factory=list)
    bearish_points: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    raw_output_path: Optional[str] = None


class ResearchRun(BaseModel):
    """一次完整研究任务."""

    stock_code: str
    stock_name: str = ""
    run_date: datetime = Field(default_factory=datetime.now)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    memos: list[ResearchMemo] = Field(default_factory=list)
    consensus_points: list[str] = Field(default_factory=list)
    divergence_points: list[str] = Field(default_factory=list)
    context_path: Optional[str] = None
    synthesis_path: Optional[str] = None
    decision_path: Optional[str] = None
