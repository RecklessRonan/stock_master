"""Markdown 报告片段生成器."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from stock_master.analysis.quantitative import ScoreResult


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
    """将五维评分格式化为可读文本."""
    d = score.to_dict()
    lines = [
        "### 五维量化评分\n",
        "| 维度 | 评分 |",
        "|------|------|",
    ]
    for dim, val in d.items():
        bar = "█" * int(val / 10) + "░" * (10 - int(val / 10))
        lines.append(f"| {dim} | {val} {bar} |")

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
