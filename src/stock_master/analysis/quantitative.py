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
    peer_percentile: float | None = None  # 同行分位 (0-100)
    confidence: float = 0.0  # 单因子可信度 (0-1)
    sub_factors: list[dict[str, Any]] = field(default_factory=list)  # 结构化子因子解释

    def numeric_score(self) -> float:
        return 0.0 if self.score is None else round(float(self.score), 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.numeric_score(),
            "coverage": round(self.coverage, 2),
            "status": self.status,
            "summary": self.summary,
            "metrics": self.metrics,
            "peer_percentile": self.peer_percentile,
            "confidence": round(self.confidence, 3),
            "sub_factors": self.sub_factors,
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


def _factor_confidence(coverage: float, status: str, peer_percentile: float | None) -> float:
    """计算单因子可信度: coverage * base + peer 加成."""
    base = 0.8 if status == "ok" else 0.0
    conf = coverage * base
    if peer_percentile is not None:
        conf += 0.2
    return min(conf, 1.0)


def _make_missing_factor(name: str, summary: str) -> FactorScore:
    return FactorScore(name=name, score=None, coverage=0.0, status="missing", summary=summary)


def _quality_sub(label: str, value: float | None, thresholds: list[tuple[float, float]], default: float = 20.0) -> dict[str, Any] | None:
    """为质量子因子生成结构化说明."""
    if value is None:
        return None
    sc = _score_by_thresholds(value, thresholds, default)
    if label == "ROE":
        explanation = f"ROE {value:.1f}%，{'盈利能力良好' if sc >= 65 else '盈利能力一般' if sc >= 50 else '盈利能力偏弱'}"
    elif label == "毛利率":
        explanation = f"毛利率 {value:.1f}%，{'竞争壁垒较强' if sc >= 65 else '中等水平' if sc >= 50 else '偏低'}"
    elif label == "净利率":
        explanation = f"净利率 {value:.1f}%，{'盈利质量优' if sc >= 65 else '盈利质量中' if sc >= 50 else '偏薄'}"
    elif label == "营收同比":
        explanation = f"营收同比 {value:.1f}%，{'高增长' if sc >= 80 else '稳定增长' if sc >= 65 else '增长乏力' if sc >= 50 else '收缩'}"
    elif label == "净利同比":
        explanation = f"净利同比 {value:.1f}%，{'利润高增' if sc >= 80 else '利润稳增' if sc >= 65 else '利润增长乏力' if sc >= 50 else '利润下滑'}"
    else:
        explanation = f"{label} {value:.2f}"
    return {"name": label, "value": round(value, 2), "score": sc, "explanation": explanation}


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

    thresholds_map = {
        "ROE": [(20, 90), (15, 80), (10, 65), (5, 50), (0, 35)],
        "毛利率": [(40, 90), (30, 80), (20, 65), (10, 50), (0, 35)],
        "净利率": [(20, 90), (12, 80), (8, 65), (3, 50), (0, 35)],
        "营收同比": [(25, 90), (15, 80), (8, 65), (0, 50), (-10, 35)],
        "净利同比": [(25, 90), (15, 80), (8, 65), (0, 50), (-10, 35)],
    }

    scores = []
    sub_factors: list[dict[str, Any]] = []
    for label in ("ROE", "毛利率", "净利率", "营收同比", "净利同比"):
        val = metrics[label]
        if val is None:
            continue
        th = thresholds_map[label]
        sc = _score_by_thresholds(val, th)
        scores.append(sc)
        sf = _quality_sub(label, val, th)
        if sf:
            sub_factors.append(sf)

    score = sum(scores) / len(scores)
    coverage = len(available) / len(metrics)
    status = "ok"
    return FactorScore(
        name="质量",
        score=_clamp(score),
        coverage=coverage,
        status=status,
        summary="盈利质量与增长质量整体可读。",
        metrics={k: round(v, 2) for k, v in available.items()},
        confidence=_factor_confidence(coverage, status, None),
        sub_factors=sub_factors,
    )


def score_value(
    valuation: dict,
    valuation_history: pd.DataFrame | None = None,
    *,
    peer_percentile: float | None = None,
) -> FactorScore:
    pe = _coerce_float(valuation.get("pe_ttm") or valuation.get("pe"))
    pb = _coerce_float(valuation.get("pb"))
    metrics: dict[str, Any] = {}
    scores: list[float] = []
    sub_factors: list[dict[str, Any]] = []

    if pe is not None:
        metrics["PE(TTM)"] = round(pe, 2)
        pe_score = _score_by_thresholds(-pe, [(-12, 90), (-18, 78), (-25, 65), (-40, 45)], default=25)
        scores.append(pe_score)
        level = "低估" if pe_score >= 78 else "合理" if pe_score >= 55 else "偏高"
        sub_factors.append({"name": "PE(TTM)", "value": round(pe, 2), "score": pe_score, "explanation": f"PE {pe:.1f}，估值{level}"})
    if pb is not None:
        metrics["PB"] = round(pb, 2)
        pb_score = _score_by_thresholds(-pb, [(-1.2, 90), (-2.0, 78), (-3.0, 65), (-5.0, 45)], default=25)
        scores.append(pb_score)
        level = "低估" if pb_score >= 78 else "合理" if pb_score >= 55 else "偏高"
        sub_factors.append({"name": "PB", "value": round(pb, 2), "score": pb_score, "explanation": f"PB {pb:.2f}，估值{level}"})
    if valuation_history is not None and not valuation_history.empty and pe is not None:
        history_col = "pe_ttm" if "pe_ttm" in valuation_history.columns else "pe"
        if history_col in valuation_history.columns:
            percentile = _compute_percentile(valuation_history[history_col], pe)
            if percentile is not None:
                metrics["PE历史分位"] = round(percentile, 1)
                hist_score = _inverse_percentile_score(percentile)
                scores.append(hist_score)
                sub_factors.append({"name": "PE历史分位", "value": round(percentile, 1), "score": hist_score, "explanation": f"当前 PE 处于历史 {percentile:.0f}% 分位"})

    if peer_percentile is not None:
        metrics["同行PE分位"] = round(peer_percentile, 1)
        peer_score = _inverse_percentile_score(peer_percentile)
        scores.append(peer_score)
        sub_factors.append({"name": "同行PE分位", "value": round(peer_percentile, 1), "score": peer_score, "explanation": f"PE 在同行中处于 {peer_percentile:.0f}% 分位"})

    if not scores:
        return _make_missing_factor("估值", "缺少估值与历史分位数据。")

    coverage = len(scores) / 3
    status = "ok"
    return FactorScore(
        name="估值",
        score=_clamp(sum(scores) / len(scores)),
        coverage=coverage,
        status=status,
        summary="当前估值结合绝对水平与历史位置综合判断。",
        metrics=metrics,
        peer_percentile=peer_percentile,
        confidence=_factor_confidence(coverage, status, peer_percentile),
        sub_factors=sub_factors,
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

    sub_factors: list[dict[str, Any]] = []

    pct20_score = _score_by_thresholds(pct_20, [(15, 90), (8, 80), (0, 65), (-8, 40)], default=20)
    scores = [pct20_score]
    metrics: dict[str, Any] = {"20日涨跌幅": round(pct_20, 2)}
    sub_factors.append({"name": "20日涨跌幅", "value": round(pct_20, 2), "score": pct20_score, "explanation": f"近20日{'上涨' if pct_20 >= 0 else '下跌'} {abs(pct_20):.1f}%"})

    if pct_60 is not None:
        pct60_score = _score_by_thresholds(pct_60, [(30, 90), (15, 80), (0, 65), (-10, 40)], default=20)
        scores.append(pct60_score)
        metrics["60日涨跌幅"] = round(pct_60, 2)
        sub_factors.append({"name": "60日涨跌幅", "value": round(pct_60, 2), "score": pct60_score, "explanation": f"近60日{'上涨' if pct_60 >= 0 else '下跌'} {abs(pct_60):.1f}%"})
    if ma20 is not None:
        ma_score = 80 if current >= ma20 else 35
        scores.append(ma_score)
        metrics["MA20"] = round(ma20, 2)
        sub_factors.append({"name": "MA20位置", "value": round(ma20, 2), "score": ma_score, "explanation": f"当前价{'站上' if current >= ma20 else '跌破'} 20日均线"})
    if rsi14 is not None:
        rsi_score = 75 if 45 <= rsi14 <= 70 else 50 if 35 <= rsi14 <= 80 else 30
        scores.append(rsi_score)
        metrics["RSI14"] = round(rsi14, 2)
        zone = "适中区间" if 45 <= rsi14 <= 70 else "偏热区间" if rsi14 > 70 else "偏冷区间"
        sub_factors.append({"name": "RSI14", "value": round(rsi14, 2), "score": rsi_score, "explanation": f"RSI {rsi14:.1f}，处于{zone}"})

    coverage = min(len(scores) / 4, 1.0)
    status = "ok"
    return FactorScore(
        name="趋势",
        score=_clamp(sum(scores) / len(scores)),
        coverage=coverage,
        status=status,
        summary="趋势结合价格强弱、均线位置与 RSI 状态。",
        metrics=metrics,
        confidence=_factor_confidence(coverage, status, None),
        sub_factors=sub_factors,
    )


def score_risk(kline: pd.DataFrame, financial: pd.DataFrame | None = None) -> FactorScore:
    latest = _latest_row(financial)
    metrics: dict[str, Any] = {}
    scores: list[float] = []
    sub_factors: list[dict[str, Any]] = []

    if not kline.empty and len(kline) >= 20:
        close = kline["收盘"]
        returns = close.pct_change().dropna()
        if not returns.empty:
            volatility = float(returns.std() * (252**0.5) * 100)
            max_price = close.rolling(window=min(60, len(close))).max()
            drawdown = float(((close - max_price) / max_price * 100).min())
            vol_score = _score_by_thresholds(-volatility, [(-20, 90), (-30, 75), (-40, 60), (-55, 40)], default=20)
            dd_score = _score_by_thresholds(drawdown, [(-10, 90), (-20, 75), (-30, 55), (-40, 35)], default=20)
            scores.append(vol_score)
            scores.append(dd_score)
            metrics["年化波动率"] = round(volatility, 2)
            metrics["最大回撤"] = round(drawdown, 2)
            sub_factors.append({"name": "年化波动率", "value": round(volatility, 2), "score": vol_score, "explanation": f"年化波动率 {volatility:.1f}%，{'波动可控' if vol_score >= 60 else '波动较大'}"})
            sub_factors.append({"name": "最大回撤", "value": round(drawdown, 2), "score": dd_score, "explanation": f"近期最大回撤 {drawdown:.1f}%，{'回撤可控' if dd_score >= 60 else '回撤偏大'}"})

    debt_ratio = _coerce_float(latest.get("资产负债率(%)"))
    current_ratio = _coerce_float(latest.get("流动比率"))
    if debt_ratio is not None:
        debt_score = _score_by_thresholds(-debt_ratio, [(-25, 90), (-40, 75), (-55, 60), (-70, 40)], default=20)
        scores.append(debt_score)
        metrics["资产负债率"] = round(debt_ratio, 2)
        sub_factors.append({"name": "资产负债率", "value": round(debt_ratio, 2), "score": debt_score, "explanation": f"资产负债率 {debt_ratio:.1f}%，{'财务稳健' if debt_score >= 60 else '杠杆偏高'}"})
    if current_ratio is not None:
        cr_score = _score_by_thresholds(current_ratio, [(2.0, 90), (1.5, 80), (1.0, 65), (0.8, 45)], default=25)
        scores.append(cr_score)
        metrics["流动比率"] = round(current_ratio, 2)
        sub_factors.append({"name": "流动比率", "value": round(current_ratio, 2), "score": cr_score, "explanation": f"流动比率 {current_ratio:.2f}，{'短期偿债能力良好' if cr_score >= 65 else '短期偿债压力较大'}"})

    if not scores:
        return _make_missing_factor("风险", "缺少波动、回撤和财务安全数据。")

    coverage = min(len(scores) / 4, 1.0)
    status = "ok"
    return FactorScore(
        name="风险",
        score=_clamp(sum(scores) / len(scores)),
        coverage=coverage,
        status=status,
        summary="风险维度越高代表回撤与财务压力越可控。",
        metrics=metrics,
        confidence=_factor_confidence(coverage, status, None),
        sub_factors=sub_factors,
    )


def score_catalyst(news: list[dict] | None = None) -> FactorScore:
    if not news:
        return _make_missing_factor("催化剂", "近期待跟踪催化剂与公告较少。")

    positive = 0
    negative = 0
    sub_factors: list[dict[str, Any]] = []
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

    sub_factors.append({"name": "正向事件", "value": positive, "score": min(positive * 25, 100), "explanation": f"识别到 {positive} 条正向催化事件"})
    sub_factors.append({"name": "负向事件", "value": negative, "score": max(100 - negative * 25, 0), "explanation": f"识别到 {negative} 条负向风险事件"})
    sub_factors.append({"name": "新闻覆盖", "value": len(news), "score": min(len(news) * 20, 100), "explanation": f"共分析 {len(news)} 条新闻"})

    coverage = 1.0
    return FactorScore(
        name="催化剂",
        score=_clamp(score),
        coverage=coverage,
        status=status,
        summary=summary,
        metrics={"正向事件": positive, "负向事件": negative, "新闻条数": len(news)},
        confidence=_factor_confidence(coverage, status, None),
        sub_factors=sub_factors,
    )


def _compute_peer_pe_percentile(pe: float | None, peers: list[dict]) -> float | None:
    """计算当前股 PE 在同行中的百分位."""
    if pe is None or not peers:
        return None
    peer_pes = []
    for p in peers:
        v = _coerce_float(p.get("pe_ttm") or p.get("pe"))
        if v is not None and v > 0:
            peer_pes.append(v)
    if not peer_pes:
        return None
    below = sum(1 for x in peer_pes if x <= pe)
    return round(below / len(peer_pes) * 100, 1)


def compute_score(
    kline: pd.DataFrame,
    valuation: dict,
    *,
    financial: pd.DataFrame | None = None,
    valuation_history: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    peers: list[dict] | None = None,
) -> ScoreResult:
    """计算升级版多因子综合评分."""

    peer_pe_pct: float | None = None
    if peers:
        pe = _coerce_float(valuation.get("pe_ttm") or valuation.get("pe"))
        peer_pe_pct = _compute_peer_pe_percentile(pe, peers)

    factors = {
        "质量": score_quality(financial),
        "估值": score_value(valuation, valuation_history=valuation_history, peer_percentile=peer_pe_pct),
        "趋势": score_trend(kline),
        "风险": score_risk(kline, financial=financial),
        "催化剂": score_catalyst(news),
    }
    return ScoreResult(factors=factors)
