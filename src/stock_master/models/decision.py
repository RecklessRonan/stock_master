"""决策与交易意图领域对象."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    REDUCE = "reduce"
    SELL = "sell"
    AVOID = "avoid"


class DecisionMemo(BaseModel):
    """人类最终投资判断."""

    stock_code: str
    stock_name: str = ""
    verdict: Verdict
    rationale: str
    planned_position_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    entry_trigger: str = ""
    invalidation_trigger: str = ""
    expected_hold_period: str = ""
    review_date: Optional[date] = None
    confidence: int = Field(default=5, ge=1, le=10)
    research_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    ADD = "add"
    REDUCE = "reduce"


class TradeIntent(BaseModel):
    """计划中的交易动作（尚未执行）."""

    stock_code: str
    stock_name: str = ""
    action: TradeAction
    target_price: Optional[float] = None
    shares: Optional[int] = None
    amount: Optional[float] = None
    reason: str = ""
    decision_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    executed: bool = False
