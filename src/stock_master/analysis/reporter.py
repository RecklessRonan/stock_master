"""Markdown 报告片段生成器."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from stock_master.analysis.quantitative import ScoreResult
from stock_master.models.research import EvidenceCoverage, RookieAction


def format_kline_summary(df: pd.DataFrame, recent_days: int = 30) -> str:
    """将近期 K 线汇总为可读文本."""
    if df.empty:
        return "暂无 K 线数据。\n"

    tail = df.tail(recent_days)
    latest = df.iloc[-1]
    first = tail.iloc[0]

    pct_change = (latest["收盘"] / first["收盘"] - 1) * 100 if first["收盘"] > 0 else 0
    highest = tail["最高"].max()
    lowest = tail["最低"].min()
    avg_vol = tail["成交量"].mean()

    lines = [
        f"### 近 {recent_days} 交易日行情摘要\n",
        f"- 最新收盘价：{latest['收盘']:.2f}",
        f"- 区间涨跌幅：{pct_change:+.2f}%",
        f"- 区间最高/最低：{highest:.2f} / {lowest:.2f}",
        f"- 平均成交量：{avg_vol:,.0f}",
    ]

    for col in ["MA5", "MA10", "MA20", "MA60"]:
        if col in df.columns and pd.notna(latest.get(col)):
            lines.append(f"- {col}：{latest[col]:.2f}")

    if "RSI14" in df.columns and pd.notna(latest.get("RSI14")):
        lines.append(f"- RSI(14)：{latest['RSI14']:.1f}")

    if "MACD_DIF" in df.columns and pd.notna(latest.get("MACD_DIF")):
        lines.append(f"- MACD DIF/DEA：{latest['MACD_DIF']:.3f} / {latest['MACD_DEA']:.3f}")

    return "\n".join(lines) + "\n"


def format_valuation_summary(val: dict) -> str:
    """将估值数据格式化为可读文本."""
    if not val:
        return "暂无估值数据。\n"

    lines = ["### 估值指标\n"]
    mapping = {
        "pe": "PE",
        "pe_ttm": "PE(TTM)",
        "pb": "PB",
        "ps": "PS",
        "ps_ttm": "PS(TTM)",
        "dv_ratio": "股息率(%)",
        "total_mv": "总市值(亿)",
    }
    for key, label in mapping.items():
        v = val.get(key)
        if v is not None:
            try:
                lines.append(f"- {label}：{float(v):.2f}")
            except (TypeError, ValueError):
                lines.append(f"- {label}：{v}")

    return "\n".join(lines) + "\n"


def format_score_summary(score: ScoreResult) -> str:
    """将升级版因子评分格式化为可读文本."""
    d = score.to_dict()
    lines = [
        "### 因子评分\n",
        "| 维度 | 评分 |",
        "|------|------|",
    ]
    for dim in ("质量", "估值", "趋势", "风险", "催化剂"):
        factor = score.factors[dim]
        if factor.status == "missing":
            lines.append(f"| {dim} | N/A ▒▒▒▒▒▒▒▒▒▒ |")
        else:
            val = d[dim]
            bar = "█" * int(val / 10) + "░" * (10 - int(val / 10))
            lines.append(f"| {dim} | {val} {bar} |")
    overall = d["综合"]
    overall_bar = "█" * int(overall / 10) + "░" * (10 - int(overall / 10))
    lines.append(f"| 综合 | {overall} {overall_bar} |")
    lines.append(f"\n- 可信度：{d['可信度']:.1f}/100")

    for name, factor in score.factors.items():
        coverage_pct = factor.coverage * 100
        lines.append(
            f"- {name}：{factor.summary}（覆盖度 {coverage_pct:.0f}% / 状态 {factor.status}）"
        )

    return "\n".join(lines) + "\n"


def format_stock_info(info: dict) -> str:
    """将股票基本信息格式化."""
    if not info or "error" in info:
        return "暂无股票基本信息。\n"

    lines = ["### 基本信息\n"]
    for k, v in info.items():
        lines.append(f"- {k}：{v}")

    return "\n".join(lines) + "\n"


def format_news_summary(news: list[dict], limit: int = 5) -> str:
    """将新闻列表格式化."""
    if not news:
        return "暂无近期新闻。\n"

    lines = ["### 近期新闻\n"]
    for item in news[:limit]:
        title = item.get("title", "无标题")
        time_str = item.get("time", "")
        source = item.get("source", "")
        lines.append(f"- **{title}** ({source}, {time_str})")

    return "\n".join(lines) + "\n"


def format_financial_summary(df: Optional[pd.DataFrame]) -> str:
    """将财务摘要格式化."""
    if df is None or df.empty:
        return "暂无财务摘要数据。\n"

    lines = ["### 财务摘要\n"]
    lines.append(df.to_markdown(index=False))
    return "\n".join(lines) + "\n"


def format_evidence_coverage(coverage: EvidenceCoverage) -> str:
    """格式化证据覆盖度."""
    lines = [
        "### 证据覆盖度\n",
        f"- 覆盖率：{coverage.coverage_ratio * 100:.0f}%",
    ]
    if coverage.available_sections:
        lines.append(f"- 已覆盖：{', '.join(coverage.available_sections)}")
    if coverage.missing_sections:
        lines.append(f"- 缺失项：{', '.join(coverage.missing_sections)}")
    if coverage.stale_sections:
        lines.append(f"- 时效不足：{', '.join(coverage.stale_sections)}")
    return "\n".join(lines) + "\n"


def format_valuation_history_summary(history: Optional[pd.DataFrame], valuation: dict) -> str:
    """格式化估值历史分位."""
    if history is None or history.empty:
        return "暂无估值历史分位数据。\n"

    current = valuation.get("pe_ttm") or valuation.get("pe")
    lines = ["### 估值历史分位\n"]
    if current is not None and "pe_ttm" in history.columns:
        series = pd.to_numeric(history["pe_ttm"], errors="coerce").dropna()
        if not series.empty:
            percentile = (series <= float(current)).mean() * 100
            lines.append(f"- 当前 PE(TTM)：{float(current):.2f}")
            lines.append(f"- 近历史分位：{percentile:.1f}%")
    if "pb" in history.columns:
        series = pd.to_numeric(history["pb"], errors="coerce").dropna()
        if not series.empty and valuation.get("pb") is not None:
            percentile = (series <= float(valuation["pb"])).mean() * 100
            lines.append(f"- 当前 PB：{float(valuation['pb']):.2f}")
            lines.append(f"- PB 历史分位：{percentile:.1f}%")
    return "\n".join(lines) + "\n"


def format_macro_summary(macro: dict[str, Any]) -> str:
    """格式化宏观快照."""
    if not macro:
        return "暂无宏观快照数据。\n"

    lines = ["### 宏观快照\n"]
    for key, value in macro.items():
        lines.append(f"- {key}：{value}")
    return "\n".join(lines) + "\n"


def format_peer_benchmark(peers: list[dict[str, Any]]) -> str:
    """格式化同行对比."""
    if not peers:
        return "暂无同行对比数据。\n"

    frame = pd.DataFrame(peers)
    lines = ["### 同行对比\n", frame.to_markdown(index=False)]
    return "\n".join(lines) + "\n"


def format_rookie_action(action: RookieAction) -> str:
    """格式化新手行动建议."""
    lines = [
        "### 新手行动建议\n",
        f"- 当前结论：{action.verdict}",
        f"- 建议单票上限：{action.max_position_pct:.1f}%",
        f"- 更适合的持有节奏：{action.preferred_holding_period}",
    ]
    if action.checklist:
        lines.append("- 买入前检查：")
        lines.extend(f"  - {item}" for item in action.checklist)
    if action.warnings:
        lines.append("- 风险提醒：")
        lines.extend(f"  - {item}" for item in action.warnings)
    return "\n".join(lines) + "\n"
