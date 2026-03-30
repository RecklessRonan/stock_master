"""研究流程领域对象."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    MARKET_DATA = "market_data"
    FINANCIAL = "financial"
    NEWS = "news"
    ANNOUNCEMENT = "announcement"
    KLINE_IMAGE = "kline_image"
    ANALYST_REPORT = "analyst_report"
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
