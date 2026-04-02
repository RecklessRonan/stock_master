"""升级版多因子评分体系."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

FACTOR_WEIGHTS = {
    "质量": 0.28,
    "估值": 0.22,
    "趋势": 0.20,
    "风险": 0.20,
    "催化剂": 0.10,
}

POSITIVE_CATALYST_KEYWORDS = (
    "回购",
    "增持",
    "中标",
    "新品",
    "上调",
    "突破",
    "增长",
    "买入",
)
NEGATIVE_CATALYST_KEYWORDS = (
    "减持",
    "问询",
    "处罚",
    "诉讼",
    "下调",
    "亏损",
    "风险",
    "违约",
)


@dataclass
class FactorScore:
    """单个因子维度的评分详情."""

    name: str
    score: float | None = None
    coverage: float = 0.0
    status: str = "missing"
    summary: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def numeric_score(self) -> float:
        return 0.0 if self.score is None else round(float(self.score), 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.numeric_score(),
            "coverage": round(self.coverage, 2),
            "status": self.status,
            "summary": self.summary,
            "metrics": self.metrics,
        }


@dataclass
class ScoreResult:
    """多因子评分结果."""

    factors: dict[str, FactorScore]

    @property
    def overall(self) -> float:
        weighted = 0.0
        used_weight = 0.0
        for name, factor in self.factors.items():
            if factor.score is None:
                continue
            weight = FACTOR_WEIGHTS.get(name, 0.0)
            weighted += factor.numeric_score() * weight
            used_weight += weight
        if used_weight == 0:
            return 0.0
        return round(weighted / used_weight, 1)

    @property
    def confidence(self) -> float:
        total_weight = 0.0
        covered_weight = 0.0
        for name, factor in self.factors.items():
            weight = FACTOR_WEIGHTS.get(name, 0.0)
            total_weight += weight
            covered_weight += weight * factor.coverage
        if total_weight == 0:
            return 0.0
        return round((covered_weight / total_weight) * 100, 1)

    def to_dict(self) -> dict[str, float]:
        result = {name: factor.numeric_score() for name, factor in self.factors.items()}
        result["综合"] = self.overall
        result["可信度"] = self.confidence
        return result

    def factor_details(self) -> dict[str, dict[str, Any]]:
        return {name: factor.as_dict() for name, factor in self.factors.items()}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    if isinstance(value, str):
        cleaned = (
            value.replace("%", "")
            .replace(",", "")
            .replace("倍", "")
            .replace("N/A", "")
            .strip()
        )
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _latest_row(df: pd.DataFrame | None) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    return df.iloc[0].to_dict()


def _score_by_thresholds(value: float, thresholds: list[tuple[float, float]], default: float = 20.0) -> float:
    for boundary, score in thresholds:
        if value >= boundary:
            return score
    return default


def _inverse_percentile_score(percentile: float) -> float:
    return _clamp(100 - percentile)


def _compute_percentile(series: pd.Series, current: float) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return float((clean <= current).mean() * 100)


def _make_missing_factor(name: str, summary: str) -> FactorScore:
    return FactorScore(name=name, score=None, coverage=0.0, status="missing", summary=summary)


def score_quality(financial: pd.DataFrame | None) -> FactorScore:
    latest = _latest_row(financial)
    metrics = {
        "ROE": _coerce_float(latest.get("ROE(%)")),
        "毛利率": _coerce_float(latest.get("毛利率(%)")),
        "净利率": _coerce_float(latest.get("净利率(%)")),
        "营收同比": _coerce_float(latest.get("营收同比(%)")),
        "净利同比": _coerce_float(latest.get("净利同比(%)")),
    }
    available = {k: v for k, v in metrics.items() if v is not None}
    if not available:
        return _make_missing_factor("质量", "缺少 ROE、利润率和增长数据。")

    scores = []
    if metrics["ROE"] is not None:
        scores.append(_score_by_thresholds(metrics["ROE"], [(20, 90), (15, 80), (10, 65), (5, 50), (0, 35)]))
    if metrics["毛利率"] is not None:
        scores.append(_score_by_thresholds(metrics["毛利率"], [(40, 90), (30, 80), (20, 65), (10, 50), (0, 35)]))
    if metrics["净利率"] is not None:
        scores.append(_score_by_thresholds(metrics["净利率"], [(20, 90), (12, 80), (8, 65), (3, 50), (0, 35)]))
    if metrics["营收同比"] is not None:
        scores.append(_score_by_thresholds(metrics["营收同比"], [(25, 90), (15, 80), (8, 65), (0, 50), (-10, 35)]))
    if metrics["净利同比"] is not None:
        scores.append(_score_by_thresholds(metrics["净利同比"], [(25, 90), (15, 80), (8, 65), (0, 50), (-10, 35)]))

    score = sum(scores) / len(scores)
    return FactorScore(
        name="质量",
        score=_clamp(score),
        coverage=len(available) / len(metrics),
        status="ok",
        summary="盈利质量与增长质量整体可读。",
        metrics={k: round(v, 2) for k, v in available.items()},
    )


def score_value(valuation: dict, valuation_history: pd.DataFrame | None = None) -> FactorScore:
    pe = _coerce_float(valuation.get("pe_ttm") or valuation.get("pe"))
    pb = _coerce_float(valuation.get("pb"))
    metrics: dict[str, Any] = {}
    scores: list[float] = []

    if pe is not None:
        metrics["PE(TTM)"] = round(pe, 2)
        scores.append(_score_by_thresholds(-pe, [(-12, 90), (-18, 78), (-25, 65), (-40, 45)], default=25))
    if pb is not None:
        metrics["PB"] = round(pb, 2)
        scores.append(_score_by_thresholds(-pb, [(-1.2, 90), (-2.0, 78), (-3.0, 65), (-5.0, 45)], default=25))
    if valuation_history is not None and not valuation_history.empty and pe is not None:
        history_col = "pe_ttm" if "pe_ttm" in valuation_history.columns else "pe"
        if history_col in valuation_history.columns:
            percentile = _compute_percentile(valuation_history[history_col], pe)
            if percentile is not None:
                metrics["PE历史分位"] = round(percentile, 1)
                scores.append(_inverse_percentile_score(percentile))

    if not scores:
        return _make_missing_factor("估值", "缺少估值与历史分位数据。")

    return FactorScore(
        name="估值",
        score=_clamp(sum(scores) / len(scores)),
        coverage=len(scores) / 3,
        status="ok",
        summary="当前估值结合绝对水平与历史位置综合判断。",
        metrics=metrics,
    )


def score_trend(kline: pd.DataFrame) -> FactorScore:
    if kline.empty or len(kline) < 20:
        return _make_missing_factor("趋势", "缺少足够的 K 线数据。")

    close = kline["收盘"]
    current = float(close.iloc[-1])
    pct_20 = (current / close.iloc[-20] - 1) * 100 if close.iloc[-20] > 0 else 0.0
    pct_60 = (current / close.iloc[-60] - 1) * 100 if len(kline) >= 60 and close.iloc[-60] > 0 else None
    ma20 = _coerce_float(kline["MA20"].iloc[-1]) if "MA20" in kline.columns else None
    rsi14 = _coerce_float(kline["RSI14"].iloc[-1]) if "RSI14" in kline.columns else None

    scores = [_score_by_thresholds(pct_20, [(15, 90), (8, 80), (0, 65), (-8, 40)], default=20)]
    metrics: dict[str, Any] = {"20日涨跌幅": round(pct_20, 2)}
    if pct_60 is not None:
        scores.append(_score_by_thresholds(pct_60, [(30, 90), (15, 80), (0, 65), (-10, 40)], default=20))
        metrics["60日涨跌幅"] = round(pct_60, 2)
    if ma20 is not None:
        scores.append(80 if current >= ma20 else 35)
        metrics["MA20"] = round(ma20, 2)
    if rsi14 is not None:
        scores.append(75 if 45 <= rsi14 <= 70 else 50 if 35 <= rsi14 <= 80 else 30)
        metrics["RSI14"] = round(rsi14, 2)

    return FactorScore(
        name="趋势",
        score=_clamp(sum(scores) / len(scores)),
        coverage=min(len(scores) / 4, 1.0),
        status="ok",
        summary="趋势结合价格强弱、均线位置与 RSI 状态。",
        metrics=metrics,
    )


def score_risk(kline: pd.DataFrame, financial: pd.DataFrame | None = None) -> FactorScore:
    latest = _latest_row(financial)
    metrics: dict[str, Any] = {}
    scores: list[float] = []

    if not kline.empty and len(kline) >= 20:
        close = kline["收盘"]
        returns = close.pct_change().dropna()
        if not returns.empty:
            volatility = float(returns.std() * (252**0.5) * 100)
            max_price = close.rolling(window=min(60, len(close))).max()
            drawdown = float(((close - max_price) / max_price * 100).min())
            scores.append(_score_by_thresholds(-volatility, [(-20, 90), (-30, 75), (-40, 60), (-55, 40)], default=20))
            scores.append(_score_by_thresholds(drawdown, [(-10, 90), (-20, 75), (-30, 55), (-40, 35)], default=20))
            metrics["年化波动率"] = round(volatility, 2)
            metrics["最大回撤"] = round(drawdown, 2)

    debt_ratio = _coerce_float(latest.get("资产负债率(%)"))
    current_ratio = _coerce_float(latest.get("流动比率"))
    if debt_ratio is not None:
        scores.append(_score_by_thresholds(-debt_ratio, [(-25, 90), (-40, 75), (-55, 60), (-70, 40)], default=20))
        metrics["资产负债率"] = round(debt_ratio, 2)
    if current_ratio is not None:
        scores.append(_score_by_thresholds(current_ratio, [(2.0, 90), (1.5, 80), (1.0, 65), (0.8, 45)], default=25))
        metrics["流动比率"] = round(current_ratio, 2)

    if not scores:
        return _make_missing_factor("风险", "缺少波动、回撤和财务安全数据。")

    return FactorScore(
        name="风险",
        score=_clamp(sum(scores) / len(scores)),
        coverage=min(len(scores) / 4, 1.0),
        status="ok",
        summary="风险维度越高代表回撤与财务压力越可控。",
        metrics=metrics,
    )


def score_catalyst(news: list[dict] | None = None) -> FactorScore:
    if not news:
        return _make_missing_factor("催化剂", "近期待跟踪催化剂与公告较少。")

    positive = 0
    negative = 0
    for item in news:
        text = f"{item.get('title', '')} {item.get('content', '')}"
        if any(word in text for word in POSITIVE_CATALYST_KEYWORDS):
            positive += 1
        if any(word in text for word in NEGATIVE_CATALYST_KEYWORDS):
            negative += 1

    score = 55 + positive * 12 - negative * 15
    status = "ok"
    summary = "近期事件偏中性。"
    if positive > negative:
        summary = "近期事件偏正向，存在催化剂。"
    elif negative > positive:
        summary = "近期事件偏负向，需要谨慎确认。"

    return FactorScore(
        name="催化剂",
        score=_clamp(score),
        coverage=1.0,
        status=status,
        summary=summary,
        metrics={"正向事件": positive, "负向事件": negative, "新闻条数": len(news)},
    )


def compute_score(
    kline: pd.DataFrame,
    valuation: dict,
    *,
    financial: pd.DataFrame | None = None,
    valuation_history: pd.DataFrame | None = None,
    news: list[dict] | None = None,
) -> ScoreResult:
    """计算升级版多因子综合评分."""

    factors = {
        "质量": score_quality(financial),
        "估值": score_value(valuation, valuation_history=valuation_history),
        "趋势": score_trend(kline),
        "风险": score_risk(kline, financial=financial),
        "催化剂": score_catalyst(news),
    }
    return ScoreResult(factors=factors)
