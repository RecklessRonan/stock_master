"""风控规则领域对象."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskRuleType(str, Enum):
    POSITION_LIMIT = "position_limit"
    STOP_LOSS = "stop_loss"
    SECTOR_LIMIT = "sector_limit"
    BLACKLIST = "blacklist"
    EVENT_LOCKOUT = "event_lockout"
    CUSTOM = "custom"


class RiskRule(BaseModel):
    """风控规则定义."""

    name: str
    type: RiskRuleType
    description: str = ""
    threshold: Optional[float] = None
    enabled: bool = True
    params: dict = Field(default_factory=dict)
