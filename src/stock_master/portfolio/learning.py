"""交易行为学习与偏差提示."""

from __future__ import annotations


def build_learning_report(trades: list[dict], reviews: list[dict]) -> dict:
    """从交易与复盘记录生成学习报告."""
    bias_flags: list[str] = []
    low_confidence_trades = [trade for trade in trades if int(trade.get("confidence", 5) or 5) <= 5]
    missing_review = [trade for trade in trades if not trade.get("review_date")]

    if len(trades) >= 4:
        bias_flags.append("近期交易次数偏多，需警惕过度交易。")
    if low_confidence_trades and len(low_confidence_trades) >= max(1, len(trades) // 2):
        bias_flags.append("低信心交易占比较高，说明入场标准可能偏松。")
    if missing_review and not reviews:
        bias_flags.append("多数交易缺少复盘安排，学习闭环尚未形成。")

    recommendations = [
        "每周至少做一次组合复盘。",
        "低于 6 分信心的交易先写清楚为什么还要下单。",
        "连续亏损时优先减少交易频率，而不是加码翻本。",
    ]

    return {
        "trade_count": len(trades),
        "review_count": len(reviews),
        "bias_flags": bias_flags,
        "recommendations": recommendations,
    }
