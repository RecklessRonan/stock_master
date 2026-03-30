"""五维量化评分体系."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ScoreResult:
    """五维评分结果."""

    growth: float = 0.0
    profitability: float = 0.0
    safety: float = 0.0
    valuation: float = 0.0
    momentum: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.growth * 0.25
            + self.profitability * 0.25
            + self.safety * 0.20
            + self.valuation * 0.15
            + self.momentum * 0.15
        )

    def to_dict(self) -> dict:
        return {
            "成长性": round(self.growth, 1),
            "盈利能力": round(self.profitability, 1),
            "安全性": round(self.safety, 1),
            "估值": round(self.valuation, 1),
            "动量": round(self.momentum, 1),
            "综合": round(self.total, 1),
        }


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_growth(kline: pd.DataFrame) -> float:
    """基于近期涨幅与均线趋势的成长性评分."""
    if kline.empty or len(kline) < 60:
        return 50.0
    close = kline["收盘"]
    pct_60 = (close.iloc[-1] / close.iloc[-60] - 1) * 100 if close.iloc[-60] > 0 else 0

    score = 50.0
    if pct_60 > 30:
        score = 85
    elif pct_60 > 15:
        score = 70
    elif pct_60 > 0:
        score = 55
    elif pct_60 > -15:
        score = 40
    else:
        score = 25

    if len(kline) >= 20 and "MA20" in kline.columns:
        ma20 = kline["MA20"].iloc[-1]
        if close.iloc[-1] > ma20:
            score += 5
        else:
            score -= 5

    return _clamp(score)


def score_profitability(valuation: dict) -> float:
    """基于 ROE 和利润率的盈利能力评分."""
    pe = valuation.get("pe_ttm") or valuation.get("pe")
    if pe is None:
        return 50.0

    score = 50.0
    try:
        pe_val = float(pe)
        if 0 < pe_val < 15:
            score = 80
        elif 15 <= pe_val < 25:
            score = 65
        elif 25 <= pe_val < 40:
            score = 50
        elif pe_val >= 40:
            score = 30
        elif pe_val < 0:
            score = 20
    except (TypeError, ValueError):
        pass

    return _clamp(score)


def score_safety(kline: pd.DataFrame) -> float:
    """基于波动率和回撤的安全性评分."""
    if kline.empty or len(kline) < 60:
        return 50.0

    close = kline["收盘"]
    returns = close.pct_change().dropna()
    volatility = returns.std() * (252**0.5) * 100

    max_price = close.rolling(window=60).max()
    drawdown = ((close - max_price) / max_price * 100).min()

    score = 50.0
    if volatility < 20:
        score += 20
    elif volatility < 35:
        score += 10
    elif volatility > 50:
        score -= 15

    if drawdown > -10:
        score += 15
    elif drawdown > -20:
        score += 5
    elif drawdown < -30:
        score -= 10

    return _clamp(score)


def score_valuation(valuation: dict) -> float:
    """基于 PE/PB 的估值评分."""
    score = 50.0

    pe = valuation.get("pe_ttm") or valuation.get("pe")
    pb = valuation.get("pb")

    if pe is not None:
        try:
            pe_val = float(pe)
            if 0 < pe_val < 12:
                score += 15
            elif 12 <= pe_val < 20:
                score += 8
            elif 20 <= pe_val < 35:
                score -= 5
            elif pe_val >= 35:
                score -= 15
        except (TypeError, ValueError):
            pass

    if pb is not None:
        try:
            pb_val = float(pb)
            if 0 < pb_val < 1.5:
                score += 10
            elif 1.5 <= pb_val < 3:
                score += 5
            elif pb_val >= 5:
                score -= 10
        except (TypeError, ValueError):
            pass

    return _clamp(score)


def score_momentum(kline: pd.DataFrame) -> float:
    """基于近期量价的动量评分."""
    if kline.empty or len(kline) < 20:
        return 50.0

    close = kline["收盘"]
    volume = kline["成交量"]

    pct_5 = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if close.iloc[-5] > 0 else 0
    pct_20 = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if close.iloc[-20] > 0 else 0

    vol_ratio = volume.iloc[-5:].mean() / volume.iloc[-20:].mean() if volume.iloc[-20:].mean() > 0 else 1

    score = 50.0
    if pct_5 > 5:
        score += 15
    elif pct_5 > 0:
        score += 5
    elif pct_5 < -5:
        score -= 10

    if pct_20 > 10:
        score += 10
    elif pct_20 < -10:
        score -= 10

    if vol_ratio > 1.5:
        score += 5
    elif vol_ratio < 0.6:
        score -= 5

    return _clamp(score)


def compute_score(kline: pd.DataFrame, valuation: dict) -> ScoreResult:
    """计算五维综合评分."""
    return ScoreResult(
        growth=score_growth(kline),
        profitability=score_profitability(valuation),
        safety=score_safety(kline),
        valuation=score_valuation(valuation),
        momentum=score_momentum(kline),
    )
