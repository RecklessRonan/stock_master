"""交易行为学习与偏差提示."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import yaml


RULES_PATH = Path("journal/personal_rules.yaml")


# ---------------------------------------------------------------------------
# 3a. 行为偏差全面检测
# ---------------------------------------------------------------------------

def detect_behavioral_biases(trades: list[dict], portfolio: dict) -> list[dict]:
    """检测交易行为偏差：过度交易、追涨杀跌、注意力驱动、频繁换股、补跌、过早止盈."""
    biases: list[dict] = []

    # --- 过度交易 ---
    month_counts: dict[str, int] = {}
    for t in trades:
        d = t.get("date", "")
        if d:
            month = d[:7]
            month_counts[month] = month_counts.get(month, 0) + 1
    for month, cnt in month_counts.items():
        if cnt >= 4:
            biases.append({
                "bias_type": "过度交易",
                "severity": "高" if cnt >= 6 else "中",
                "description": f"{month} 交易 {cnt} 次，交易频率偏高。",
                "recommendation": "降低交易频率，每月不超过 3 次，专注于高确信度机会。",
            })

    # --- 追涨杀跌 ---
    for t in trades:
        action = t.get("action", "")
        price = float(t.get("price", 0) or 0)
        recent_high = float(t.get("recent_high", 0) or 0)
        recent_low = float(t.get("recent_low", 0) or 0)
        if action == "buy" and recent_high > 0 and price > 0:
            if price / recent_high > 0.95:
                biases.append({
                    "bias_type": "追涨",
                    "severity": "高",
                    "description": f"{t.get('code', '')} 买入价 {price} 接近近期高点 {recent_high}。",
                    "recommendation": "避免在高位追入，等待回调确认后再建仓。",
                })
        if action == "sell" and recent_low > 0 and price > 0:
            if price / recent_low < 1.05:
                biases.append({
                    "bias_type": "杀跌",
                    "severity": "高",
                    "description": f"{t.get('code', '')} 卖出价 {price} 接近近期低点 {recent_low}。",
                    "recommendation": "低位恐慌卖出往往锁定亏损，先评估论点是否失效。",
                })

    # --- 注意力驱动（无研究引用的交易）---
    no_research = [t for t in trades if not t.get("research_ref")]
    if no_research and len(no_research) >= max(1, len(trades) // 2):
        biases.append({
            "bias_type": "注意力驱动",
            "severity": "中",
            "description": f"{len(no_research)}/{len(trades)} 笔交易缺少研究引用，可能凭直觉交易。",
            "recommendation": "每笔交易前完成研究报告或至少记录决策逻辑。",
        })

    # --- 频繁换股 ---
    code_actions: dict[str, list[str]] = {}
    for t in trades:
        code = t.get("code", "")
        action = t.get("action", "")
        if code:
            code_actions.setdefault(code, []).append(action)
    short_hold = sum(
        1 for acts in code_actions.values()
        if "buy" in acts and "sell" in acts and len(acts) <= 3
    )
    if short_hold >= 2:
        biases.append({
            "bias_type": "频繁换股",
            "severity": "中",
            "description": f"{short_hold} 只股票短期内买卖完毕，持有周期过短。",
            "recommendation": "延长持有周期，给投资论点足够的验证时间。",
        })

    # --- 补跌倾向 ---
    positions = portfolio.get("positions", [])
    for pos in positions:
        avg_cost = float(pos.get("avg_cost", 0) or 0)
        current_price = float(pos.get("current_price", avg_cost) or avg_cost)
        if avg_cost > 0 and current_price < avg_cost * 0.85:
            add_count = sum(
                1 for t in trades
                if t.get("code") == pos.get("code") and t.get("action") == "add"
            )
            if add_count >= 1:
                biases.append({
                    "bias_type": "补跌倾向",
                    "severity": "高",
                    "description": f"{pos.get('code', '')} 浮亏 {((current_price/avg_cost-1)*100):.1f}% 仍在加仓。",
                    "recommendation": "浮亏超过 15% 时不宜盲目补仓，先确认基本面未恶化。",
                })

    # --- 过早止盈 ---
    for t in trades:
        if t.get("action") == "sell":
            buy_price = float(t.get("buy_price", 0) or 0)
            sell_price = float(t.get("price", 0) or 0)
            if buy_price > 0 and sell_price > buy_price:
                gain_pct = (sell_price - buy_price) / buy_price * 100
                if 0 < gain_pct < 5:
                    biases.append({
                        "bias_type": "过早止盈",
                        "severity": "低",
                        "description": f"{t.get('code', '')} 盈利仅 {gain_pct:.1f}% 即卖出。",
                        "recommendation": "让盈利奔跑，考虑用移动止盈替代固定止盈。",
                    })

    return biases


# ---------------------------------------------------------------------------
# 3b. 个人规则库
# ---------------------------------------------------------------------------

def load_personal_rules() -> list[dict]:
    """从 YAML 文件加载个人规则."""
    if not RULES_PATH.exists():
        return []
    with open(RULES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, list) else []


def save_personal_rule(rule: dict) -> None:
    """保存一条个人规则到 YAML 文件."""
    rules = load_personal_rules()
    if "id" not in rule:
        rule["id"] = uuid.uuid4().hex[:8]
    if "active" not in rule:
        rule["active"] = True
    if "created_at" not in rule:
        rule["created_at"] = datetime.now().isoformat()
    rules.append(rule)
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(
        yaml.dump(rules, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def suggest_rules_from_history(trades: list[dict], reviews: list[dict]) -> list[dict]:
    """根据交易和复盘记录自动建议个人规则."""
    suggestions: list[dict] = []

    loss_trades = [
        t for t in trades
        if t.get("action") == "sell"
        and float(t.get("price", 0) or 0) < float(t.get("buy_price", 0) or 0)
    ]
    if len(loss_trades) >= 2:
        suggestions.append({
            "id": uuid.uuid4().hex[:8],
            "type": "止损",
            "description": "亏损交易较多，建议每笔交易设定明确止损位（如 -8%）。",
            "created_from": "历史亏损分析",
            "active": True,
        })

    no_research = [t for t in trades if not t.get("research_ref")]
    if len(no_research) >= 2:
        suggestions.append({
            "id": uuid.uuid4().hex[:8],
            "type": "研究纪律",
            "description": "多笔交易缺少研究引用，建议建仓前必须完成研究报告。",
            "created_from": "无研究引用交易分析",
            "active": True,
        })

    no_review = [t for t in trades if not t.get("review_date")]
    if len(no_review) >= 3:
        suggestions.append({
            "id": uuid.uuid4().hex[:8],
            "type": "复盘纪律",
            "description": "多数交易未安排复盘，建议每笔交易结束后一周内复盘。",
            "created_from": "未复盘交易分析",
            "active": True,
        })

    # 从复盘中提取教训
    lesson_keywords = ["教训", "错误", "不应该", "失误", "下次"]
    for r in reviews:
        content = r.get("content", "")
        if any(kw in content for kw in lesson_keywords):
            suggestions.append({
                "id": uuid.uuid4().hex[:8],
                "type": "复盘教训",
                "description": f"复盘 {r.get('code', '')} 中提到教训，建议固化为规则。",
                "created_from": f"复盘记录 {r.get('date', '')}",
                "active": True,
            })

    return suggestions


# ---------------------------------------------------------------------------
# 3c. 个体行为画像
# ---------------------------------------------------------------------------

def build_trader_profile(trades: list[dict], reviews: list[dict]) -> dict:
    """基于交易和复盘数据构建个体行为画像."""
    total_trades = len(trades)

    # 胜率
    sell_trades = [t for t in trades if t.get("action") == "sell"]
    wins = 0
    for t in sell_trades:
        sell_p = float(t.get("price", 0) or 0)
        buy_p = float(t.get("buy_price", 0) or 0)
        if sell_p > buy_p > 0:
            wins += 1
    win_rate = round(wins / len(sell_trades) * 100, 1) if sell_trades else 0.0

    # 平均持有天数
    holding_days: list[float] = []
    for t in sell_trades:
        buy_date = t.get("buy_date", "")
        sell_date = t.get("date", "")
        if buy_date and sell_date:
            try:
                bd = date.fromisoformat(buy_date)
                sd = date.fromisoformat(sell_date)
                holding_days.append((sd - bd).days)
            except (ValueError, TypeError):
                pass
    avg_holding_days = round(sum(holding_days) / len(holding_days), 1) if holding_days else 0.0

    # 最常交易类型
    action_counts = Counter(t.get("action", "") for t in trades)
    most_traded_type = action_counts.most_common(1)[0][0] if action_counts else "无"

    # 常见错误
    common_mistakes: list[str] = []
    if win_rate < 40 and len(sell_trades) >= 3:
        common_mistakes.append("胜率偏低，选股或择时可能存在系统性问题。")
    if avg_holding_days > 0 and avg_holding_days < 7:
        common_mistakes.append("平均持有天数过短，可能频繁短线交易。")
    no_research_pct = sum(1 for t in trades if not t.get("research_ref")) / max(total_trades, 1) * 100
    if no_research_pct > 50:
        common_mistakes.append("超过半数交易缺少研究引用，决策依据不足。")

    # 优势
    strengths: list[str] = []
    if win_rate >= 60 and len(sell_trades) >= 3:
        strengths.append("胜率较高，选股能力良好。")
    if avg_holding_days >= 30:
        strengths.append("持有周期合理，不受短期波动干扰。")
    if len(reviews) >= len(sell_trades) and len(sell_trades) > 0:
        strengths.append("复盘覆盖率高，学习闭环完善。")

    # 建议
    recommendations: list[str] = []
    if common_mistakes:
        recommendations.append("针对常见错误制定具体改进规则。")
    if not reviews:
        recommendations.append("开始建立复盘习惯，每笔交易结束后做回顾。")
    if win_rate < 50 and len(sell_trades) >= 3:
        recommendations.append("考虑提高入场标准，聚焦高确信度机会。")
    recommendations.append("定期回顾个人行为画像，追踪进步。")

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_holding_days": avg_holding_days,
        "most_traded_type": most_traded_type,
        "common_mistakes": common_mistakes,
        "strengths": strengths,
        "bias_history": [],  # 由调用方通过 detect_behavioral_biases 填充
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# 3d. 增强 build_learning_report
# ---------------------------------------------------------------------------

def build_learning_report(trades: list[dict], reviews: list[dict], portfolio: dict | None = None) -> dict:
    """从交易与复盘记录生成学习报告（增强版）."""
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

    # 增强：行为偏差检测
    behavioral_biases: list[dict] = []
    if portfolio is not None:
        behavioral_biases = detect_behavioral_biases(trades, portfolio)
        for b in behavioral_biases:
            flag = f"[{b['bias_type']}] {b['description']}"
            if flag not in bias_flags:
                bias_flags.append(flag)

    # 增强：行为画像
    profile = build_trader_profile(trades, reviews)
    profile["bias_history"] = behavioral_biases

    # 合并画像建议
    for rec in profile["recommendations"]:
        if rec not in recommendations:
            recommendations.append(rec)

    return {
        "trade_count": len(trades),
        "review_count": len(reviews),
        "bias_flags": bias_flags,
        "recommendations": recommendations,
        "behavioral_biases": behavioral_biases,
        "trader_profile": profile,
    }
