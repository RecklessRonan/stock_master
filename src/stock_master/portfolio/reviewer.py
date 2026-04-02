"""复盘系统 — 生成复盘模板与预测 vs 实际对比."""

from __future__ import annotations

from datetime import date
from pathlib import Path


REVIEWS_DIR = Path("journal/reviews")
ENTRIES_DIR = Path("journal/entries")
ATTRIBUTION_DIR = Path("journal/attributions")


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

    if filepath.exists():
        return filepath

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


# ---------------------------------------------------------------------------
# 6a. 区分买入和卖出的交易条目
# ---------------------------------------------------------------------------

def create_trade_entry(
    code: str,
    name: str,
    action: str,
    price: float,
    shares: int,
    reason: str = "",
    research_ref: str = "",
) -> Path:
    """创建交易叙事日志条目（根据 action 类型生成不同模板）."""
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

    if action in ("buy", "add"):
        lines.extend([
            "## 买入逻辑",
            "",
            reason or "<!-- 为什么买入这只股票？核心论点是什么？ -->",
            "",
            "## 失效条件",
            "",
            "<!-- 什么情况下投资论点不再成立？ -->",
            "",
            "- ",
            "",
            "## 止损价格",
            "",
            "<!-- 明确的止损位和对应仓位变动 -->",
            "",
            "- 止损价：",
            "- 止损比例：",
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
    elif action in ("sell", "reduce"):
        lines.extend([
            "## 卖出原因",
            "",
            reason or "<!-- 为什么卖出？是主动止盈/止损还是被动触发？ -->",
            "",
            "## 回顾买入逻辑",
            "",
            "<!-- 当初买入的理由是什么？论点是否被验证？ -->",
            "",
            "",
            "## 后来发生了什么",
            "",
            "<!-- 从买入到卖出期间，价格/基本面/消息面发生了什么变化？ -->",
            "",
            "",
            "## 本次交易得失",
            "",
            "<!-- 盈亏金额、持有周期、决策质量自评 -->",
            "",
            "- 盈亏：",
            "- 持有天数：",
            "- 决策质量：",
            "",
            "## 当时情绪",
            "",
            "<!-- 卖出时的心理状态 -->",
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
    else:
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


# ---------------------------------------------------------------------------
# 6b. 卖出归因报告
# ---------------------------------------------------------------------------

def create_sell_attribution(
    code: str,
    name: str,
    buy_info: dict,
    sell_info: dict,
) -> Path:
    """生成卖出归因报告：为什么买、为什么卖、后来发生了什么、错在哪."""
    ATTRIBUTION_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    filename = f"{today}-{code}-attribution.md"
    filepath = ATTRIBUTION_DIR / filename

    buy_date = buy_info.get("date", "未知")
    buy_price = buy_info.get("price", 0)
    buy_reason = buy_info.get("reason", "")
    buy_shares = buy_info.get("shares", 0)

    sell_date = sell_info.get("date", today)
    sell_price = sell_info.get("price", 0)
    sell_reason = sell_info.get("reason", "")
    sell_shares = sell_info.get("shares", 0)

    pnl = round((sell_price - buy_price) * sell_shares, 2) if buy_price and sell_price else 0
    pnl_pct = round((sell_price / buy_price - 1) * 100, 2) if buy_price > 0 else 0.0

    lines = [
        f"# 卖出归因报告：{name or code} ({code})",
        "",
        f"> 生成日期：{today}",
        f"> 买入日期：{buy_date}  |  卖出日期：{sell_date}",
        f"> 买入价：{buy_price}  |  卖出价：{sell_price}",
        f"> 盈亏：{pnl}（{pnl_pct:+.2f}%）",
        "",
        "---",
        "",
        "## 1. 为什么买入",
        "",
        f"- 日期：{buy_date}",
        f"- 价格：{buy_price}",
        f"- 数量：{buy_shares} 股",
        f"- 理由：{buy_reason or '<!-- 回顾当初的买入理由 -->'}",
        "",
        "### 当时的投资论点",
        "",
        "<!-- 核心逻辑：增长故事 / 估值修复 / 催化剂驱动？ -->",
        "",
        "",
        "## 2. 为什么卖出",
        "",
        f"- 日期：{sell_date}",
        f"- 价格：{sell_price}",
        f"- 数量：{sell_shares} 股",
        f"- 理由：{sell_reason or '<!-- 卖出的具体原因 -->'}",
        "",
        "### 卖出触发因素",
        "",
        "<!-- 止盈 / 止损 / 论点失效 / 更好机会 / 情绪驱动？ -->",
        "",
        "",
        "## 3. 持有期间发生了什么",
        "",
        "<!-- 价格走势、业绩变化、行业消息、政策影响 -->",
        "",
        "",
        "## 4. 错在哪里",
        "",
        "<!-- 买入时机、卖出时机、仓位管理、风控执行哪一环出了问题？ -->",
        "",
        "- ",
        "",
        "## 5. 做对了什么",
        "",
        "<!-- 哪些决策是正确的？ -->",
        "",
        "- ",
        "",
        "## 6. 下次改进",
        "",
        "<!-- 具体可执行的改进措施 -->",
        "",
        "- ",
        "",
        "## 7. 是否需要新增个人规则",
        "",
        "<!-- 是否需要把教训固化为个人交易规则？ -->",
        "",
        "",
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath
