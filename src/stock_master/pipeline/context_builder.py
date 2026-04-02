"""研究上下文包构建器 — 自动打包量化数据为 Markdown."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml
from rich.console import Console

from stock_master.analysis.quantitative import compute_score
from stock_master.analysis.reporter import (
    format_announcements,
    format_capital_flow,
    format_earnings_forecast,
    format_evidence_coverage,
    format_factor_details,
    format_financial_summary,
    format_kline_summary,
    format_macro_summary,
    format_news_summary,
    format_peer_benchmark,
    format_rookie_action,
    format_score_summary,
    format_shareholder_changes,
    format_stock_info,
    format_teaching_segment,
    format_valuation_history_summary,
    format_valuation_summary,
)
from stock_master.analysis.technical import (
    detect_support_resistance,
    detect_trend,
    volume_analysis,
)
from stock_master.data.cache import DataCache
from stock_master.data.fetcher import (
    fetch_announcements,
    fetch_capital_flow,
    fetch_daily_kline,
    fetch_earnings_forecast,
    fetch_financial_statements,
    fetch_financial_summary,
    fetch_macro_snapshot,
    fetch_news,
    fetch_peer_benchmark,
    fetch_shareholder_changes,
    fetch_stock_info,
    fetch_valuation,
    fetch_valuation_history,
)
from stock_master.data.indicators import add_all_indicators
from stock_master.pipeline.dossier import build_stock_dossier, generate_teaching_segment
from stock_master.pipeline.providers import summarize_data_provider_catalog

console = Console()


def build_context(
    code: str,
    output_dir: Optional[Path] = None,
    cache: Optional[DataCache] = None,
) -> Path:
    """为指定股票构建完整的研究上下文包.

    Returns:
        context.md 的文件路径
    """
    if cache is None:
        cache = DataCache()

    today = date.today().isoformat()

    if output_dir is None:
        output_dir = Path("research") / code / today
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 股票基本信息 ---
    console.print(f"[bold blue]拉取 {code} 基本信息...[/]")
    info = cache.get_info(code)
    if info is None:
        info = fetch_stock_info(code)
        if "error" not in info:
            cache.set_info(code, info)

    stock_name = info.get("股票简称", info.get("名称", code))

    # --- K 线数据 ---
    console.print(f"[bold blue]拉取 {code} K线数据...[/]")
    kline = cache.get_kline(code)
    if kline is None:
        kline = fetch_daily_kline(code)
        if not kline.empty:
            cache.set_kline(code, kline)

    if not kline.empty:
        kline = add_all_indicators(kline)

    # --- 估值 ---
    console.print(f"[bold blue]拉取 {code} 估值数据...[/]")
    valuation = cache.get_valuation(code)
    if valuation is None:
        valuation = fetch_valuation(code)
        if valuation:
            cache.set_valuation(code, valuation)

    valuation_history = cache.get_dataset(code, "valuation_history")
    if valuation_history is None:
        valuation_history = fetch_valuation_history(code)
        if valuation_history is not None and not valuation_history.empty:
            cache.set_dataset(code, "valuation_history", valuation_history)
    if valuation_history is None:
        valuation_history = pd.DataFrame()

    # --- 财务 ---
    console.print(f"[bold blue]拉取 {code} 财务摘要...[/]")
    financial = fetch_financial_summary(code)

    # --- 新闻 ---
    console.print(f"[bold blue]拉取 {code} 近期新闻...[/]")
    news = fetch_news(code)

    # --- 资金流向 ---
    console.print(f"[bold blue]拉取 {code} 资金流向...[/]")
    capital_flow = fetch_capital_flow(code)

    # --- 股东变化 ---
    console.print(f"[bold blue]拉取 {code} 股东变化...[/]")
    shareholder_changes = fetch_shareholder_changes(code)

    # --- 公告 ---
    console.print(f"[bold blue]拉取 {code} 近期公告...[/]")
    announcements = fetch_announcements(code)

    # --- 业绩预告 ---
    console.print(f"[bold blue]拉取 {code} 业绩预告...[/]")
    earnings_forecast = fetch_earnings_forecast(code)

    # --- 完整三表 ---
    console.print(f"[bold blue]拉取 {code} 完整财务报表...[/]")
    financial_statements = fetch_financial_statements(code)

    macro = cache.get_dataset(code, "macro_snapshot")
    if macro is None:
        macro = fetch_macro_snapshot(code, info=info)
        if macro:
            cache.set_dataset(code, "macro_snapshot", macro)
    if macro is None:
        macro = {}

    peers = cache.get_dataset(code, "peer_benchmark")
    if peers is None:
        peers = fetch_peer_benchmark(code, info=info)
        if peers:
            cache.set_dataset(code, "peer_benchmark", peers)
    if peers is None:
        peers = []

    # --- 升级因子评分 ---
    score = compute_score(
        kline,
        valuation,
        financial=financial,
        valuation_history=valuation_history,
        news=news,
        peers=peers,
    )

    # --- 技术面快照 ---
    trend = detect_trend(kline) if not kline.empty else "N/A"
    sr = detect_support_resistance(kline) if not kline.empty else {}
    vol_signal = volume_analysis(kline) if not kline.empty else "N/A"

    dossier = build_stock_dossier(
        code=code,
        stock_name=stock_name,
        score=score,
        info=info,
        kline=kline,
        valuation=valuation,
        financial=financial,
        news=news,
        macro=macro,
        peers=peers,
        data_sources=summarize_data_provider_catalog(),
        capital_flow=capital_flow,
        shareholder_changes=shareholder_changes,
        announcements=announcements,
        earnings_forecast=earnings_forecast,
        financial_statements=financial_statements,
        valuation_history=valuation_history,
    )

    # --- 组装 context.md ---
    sections = [
        f"# 研究上下文：{stock_name} ({code})\n",
        f"> 生成时间：{today}\n",
        format_stock_info(info),
        format_evidence_coverage(dossier.coverage),
        format_score_summary(score),
        format_valuation_summary(valuation),
        format_valuation_history_summary(valuation_history, valuation),
        format_kline_summary(kline),
        _format_tech_snapshot(trend, sr, vol_signal),
        format_financial_summary(financial),
        format_capital_flow(capital_flow),
        format_shareholder_changes(shareholder_changes),
        format_announcements(announcements),
        format_earnings_forecast(earnings_forecast),
        format_peer_benchmark(peers),
        format_macro_summary(macro),
        format_news_summary(news),
        format_rookie_action(dossier.rookie_action),
        format_factor_details(score),
        format_teaching_segment(generate_teaching_segment(score, dossier.coverage)),
    ]

    context_path = output_dir / "context.md"
    context_path.write_text("\n".join(sections), encoding="utf-8")

    dossier_path = output_dir / "dossier.yaml"
    dossier_path.write_text(
        yaml.dump(dossier.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    (output_dir / "agents").mkdir(exist_ok=True)

    console.print(f"[bold green]上下文已生成：{context_path}[/]")
    return context_path


def _format_tech_snapshot(trend: str, sr: dict, vol_signal: str) -> str:
    lines = [
        "### 技术面快照\n",
        f"- 趋势判断：{trend}",
    ]
    if sr.get("support"):
        lines.append(f"- 支撑位：{sr['support']}")
    if sr.get("resistance"):
        lines.append(f"- 阻力位：{sr['resistance']}")
    lines.append(f"- 量价信号：{vol_signal}")
    return "\n".join(lines) + "\n"
