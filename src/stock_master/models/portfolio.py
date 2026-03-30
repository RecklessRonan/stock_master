"""持仓、交易记录与复盘领域对象."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from stock_master.models.decision import TradeAction


class TradeExecution(BaseModel):
    """真实成交记录."""

    stock_code: str
    stock_name: str = ""
    action: TradeAction
    price: float
    shares: int
    amount: float = 0.0
    commission: float = 0.0
    executed_at: datetime = Field(default_factory=datetime.now)
    decision_ref: Optional[str] = None
    research_ref: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


class PositionSnapshot(BaseModel):
    """持仓快照."""

    stock_code: str
    stock_name: str = ""
    shares: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0
    strategy: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    research_ref: Optional[str] = None
    notes: str = ""

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def pnl(self) -> float:
        return (self.current_price - self.avg_cost) * self.shares

    @property
    def pnl_pct(self) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost


class ReviewLog(BaseModel):
    """复盘记录."""

    stock_code: str
    stock_name: str = ""
    review_date: date = Field(default_factory=date.today)
    original_thesis: str = ""
    what_happened: str = ""
    thesis_still_valid: bool = True
    lessons: list[str] = Field(default_factory=list)
    next_review_date: Optional[date] = None
    decision_ref: Optional[str] = None
    research_ref: Optional[str] = None
