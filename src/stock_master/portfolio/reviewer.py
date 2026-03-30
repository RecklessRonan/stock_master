"""复盘系统 — 生成复盘模板与预测 vs 实际对比."""

from __future__ import annotations

from datetime import date
from pathlib import Path


REVIEWS_DIR = Path("journal/reviews")
ENTRIES_DIR = Path("journal/entries")


def create_review_template(
    code: str,
    name: str = "",
    review_type: str = "individual",
    research_ref: str = "",
    decision_ref: str = "",
) -> Path:
    """生成复盘模板文件."""
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    if review_type == "individual":
        filename = f"{today}-{code}-review.md"
        title = f"个股复盘：{name or code} ({code})"
    elif review_type == "weekly":
        filename = f"{today}-weekly.md"
        title = f"周度复盘：{today}"
    else:
        filename = f"{today}-monthly.md"
        title = f"月度复盘：{today}"

    filepath = REVIEWS_DIR / filename

    lines = [
        f"# {title}\n",
        f"> 日期：{today}",
    ]

    if research_ref:
        lines.append(f"> 研究引用：{research_ref}")
    if decision_ref:
        lines.append(f"> 决策引用：{decision_ref}")

    lines.extend([
        "",
        "## 当时的投资论点",
        "",
        "<!-- 回顾当时为什么买入/卖出 -->",
        "",
        "",
        "## 实际发生了什么",
        "",
        "<!-- 价格、业绩、消息面实际表现 -->",
        "",
        "",
        "## 预测 vs 实际对比",
        "",
        "| 维度 | 当时预测 | 实际情况 | 偏差 |",
        "|------|----------|----------|------|",
        "| 价格 |          |          |      |",
        "| 业绩 |          |          |      |",
        "| 催化剂 |        |          |      |",
        "",
        "## 论点是否仍然有效",
        "",
        "<!-- 是/否，理由 -->",
        "",
        "",
        "## 学到了什么",
        "",
        "- ",
        "",
        "## 下一步行动",
        "",
        "- ",
        "",
        "## 下次复盘日期",
        "",
        "<!-- YYYY-MM-DD -->",
        "",
    ])

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def create_trade_entry(
    code: str,
    name: str,
    action: str,
    price: float,
    shares: int,
    reason: str = "",
    research_ref: str = "",
) -> Path:
    """创建交易叙事日志条目."""
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    filename = f"{today}-{action}-{code}.md"
    filepath = ENTRIES_DIR / filename

    lines = [
        f"# 交易记录：{action.upper()} {name or code} ({code})",
        "",
        f"> 日期：{today}",
        f"> 操作：{action} {shares} 股 @ {price}",
        f"> 金额：{round(price * shares, 2)}",
        "",
    ]

    if research_ref:
        lines.append(f"> 研究引用：{research_ref}")
        lines.append("")

    lines.extend([
        "## 决策逻辑",
        "",
        reason or "<!-- 为什么做出这个交易决策？ -->",
        "",
        "## 当时情绪",
        "",
        "<!-- 交易时的心理状态与信心水平 -->",
        "",
        "",
        "## AI 建议摘要",
        "",
        "<!-- 各模型当时给出的关键意见 -->",
        "",
        "",
        "## 备注",
        "",
        "",
    ])

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath
