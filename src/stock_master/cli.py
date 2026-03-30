"""Stock Master CLI 入口."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="sm",
    help="Stock Master — 本地优先的个人股票投资决策系统",
    no_args_is_help=True,
)
console = Console()


@app.command()
def data(
    code: str = typer.Argument(..., help="股票代码，如 002273"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="指定输出目录"),
) -> None:
    """拉取股票数据并生成研究上下文包."""
    from stock_master.pipeline.context_builder import build_context

    output_dir = Path(output) if output else None
    path = build_context(code, output_dir=output_dir)
    console.print(f"\n[bold]上下文文件：[/] {path}")
    console.print("[dim]接下来可在 Cursor 中 @ 引用 context.md 与 prompts/ 模板开始调研。[/]")


@app.command()
def score(
    code: str = typer.Argument(..., help="股票代码"),
) -> None:
    """查看股票的五维量化评分."""
    from stock_master.analysis.quantitative import compute_score
    from stock_master.data.cache import DataCache
    from stock_master.data.fetcher import fetch_daily_kline, fetch_stock_info, fetch_valuation
    from stock_master.data.indicators import add_all_indicators

    cache = DataCache()

    info = cache.get_info(code)
    if info is None:
        info = fetch_stock_info(code)
        if "error" not in info:
            cache.set_info(code, info)
    stock_name = info.get("股票简称", info.get("名称", code))

    kline = cache.get_kline(code)
    if kline is None:
        console.print("[dim]正在拉取 K 线数据...[/]")
        kline = fetch_daily_kline(code)
        if not kline.empty:
            cache.set_kline(code, kline)
            kline = add_all_indicators(kline)

    valuation = cache.get_valuation(code)
    if valuation is None:
        console.print("[dim]正在拉取估值数据...[/]")
        valuation = fetch_valuation(code)
        if valuation:
            cache.set_valuation(code, valuation)

    result = compute_score(kline, valuation)

    table = Table(title=f"{stock_name} ({code}) 五维量化评分")
    table.add_column("维度", style="cyan")
    table.add_column("评分", justify="right", style="bold")
    table.add_column("图示", style="green")

    for dim, val in result.to_dict().items():
        bar = "█" * int(val / 10) + "░" * (10 - int(val / 10))
        style = "bold red" if dim == "综合" else ""
        table.add_row(dim, f"{val:.1f}", bar, style=style)

    console.print(table)


@app.command()
def compare(
    codes: list[str] = typer.Argument(..., help="要对比的股票代码列表"),
) -> None:
    """多股对比评分."""
    from stock_master.analysis.quantitative import compute_score
    from stock_master.data.cache import DataCache
    from stock_master.data.fetcher import fetch_daily_kline, fetch_stock_info, fetch_valuation
    from stock_master.data.indicators import add_all_indicators

    cache = DataCache()

    table = Table(title="多股对比")
    table.add_column("股票", style="cyan")
    table.add_column("成长性", justify="right")
    table.add_column("盈利能力", justify="right")
    table.add_column("安全性", justify="right")
    table.add_column("估值", justify="right")
    table.add_column("动量", justify="right")
    table.add_column("综合", justify="right", style="bold")

    for code in codes:
        info = cache.get_info(code)
        if info is None:
            info = fetch_stock_info(code)
            if "error" not in info:
                cache.set_info(code, info)
        name = info.get("股票简称", info.get("名称", code))

        kline = cache.get_kline(code)
        if kline is None:
            console.print(f"[dim]拉取 {code} 数据...[/]")
            kline = fetch_daily_kline(code)
            if not kline.empty:
                cache.set_kline(code, kline)
                kline = add_all_indicators(kline)

        valuation = cache.get_valuation(code)
        if valuation is None:
            valuation = fetch_valuation(code)
            if valuation:
                cache.set_valuation(code, valuation)

        s = compute_score(kline, valuation)
        d = s.to_dict()
        table.add_row(
            f"{name}\n({code})",
            f"{d['成长性']:.1f}",
            f"{d['盈利能力']:.1f}",
            f"{d['安全性']:.1f}",
            f"{d['估值']:.1f}",
            f"{d['动量']:.1f}",
            f"{d['综合']:.1f}",
        )

    console.print(table)


@app.command()
def trade(
    action: str = typer.Argument(..., help="交易动作：buy/sell/add/reduce"),
    code: str = typer.Argument(..., help="股票代码"),
    price: float = typer.Option(..., "--price", "-p", help="成交价格"),
    shares: int = typer.Option(..., "--shares", "-s", help="成交股数"),
    reason: str = typer.Option("", "--reason", "-r", help="交易理由"),
    research_ref: str = typer.Option("", "--ref", help="关联的调研目录"),
    confidence: int = typer.Option(5, "--confidence", "-c", help="信心评分 1-10"),
    review_date: str = typer.Option("", "--review-date", help="复盘日期 YYYY-MM-DD"),
) -> None:
    """记录一笔交易."""
    from stock_master.data.cache import DataCache
    from stock_master.data.fetcher import fetch_stock_info
    from stock_master.portfolio.trade_log import record_trade
    from stock_master.portfolio.tracker import update_position
    from stock_master.portfolio.reviewer import create_trade_entry

    cache = DataCache()
    info = cache.get_info(code)
    if info is None:
        info = fetch_stock_info(code)
        if "error" not in info:
            cache.set_info(code, info)
    stock_name = info.get("股票简称", info.get("名称", code))

    trade_path = record_trade(
        code=code,
        action=action,
        price=price,
        shares=shares,
        name=stock_name,
        reason=reason,
        research_ref=research_ref,
        confidence=confidence,
        tags=[],
        review_date=review_date,
    )

    update_position(
        code=code,
        name=stock_name,
        action=action,
        price=price,
        shares=shares,
        research_ref=research_ref,
    )

    entry_path = create_trade_entry(
        code=code,
        name=stock_name,
        action=action,
        price=price,
        shares=shares,
        reason=reason,
        research_ref=research_ref,
    )

    console.print(f"[bold green]交易已记录！[/]")
    console.print(f"  📄 交易记录：{trade_path}")
    console.print(f"  📄 叙事日志：{entry_path}")
    console.print(f"  📄 持仓已更新：journal/portfolio.yaml")


@app.command()
def portfolio() -> None:
    """查看当前持仓."""
    from stock_master.portfolio.trade_log import load_portfolio

    data = load_portfolio()
    positions = data.get("positions", [])

    if not positions:
        console.print("[dim]暂无持仓。[/]")
        return

    table = Table(title=f"当前持仓（更新于 {data.get('updated_at', 'N/A')}）")
    table.add_column("股票", style="cyan")
    table.add_column("股数", justify="right")
    table.add_column("成本价", justify="right")
    table.add_column("止损", justify="right", style="red")
    table.add_column("策略", style="dim")
    table.add_column("研究引用", style="dim")

    for pos in positions:
        table.add_row(
            f"{pos.get('name', '')}\n({pos['code']})",
            str(pos.get("shares", 0)),
            f"{pos.get('avg_cost', 0):.2f}",
            f"{pos.get('stop_loss', 'N/A')}",
            pos.get("strategy", ""),
            pos.get("research_ref", ""),
        )

    console.print(table)


@app.command()
def review(
    code: str = typer.Argument("", help="股票代码（留空则创建周度复盘）"),
    review_type: str = typer.Option("individual", "--type", "-t", help="复盘类型：individual/weekly/monthly"),
    research_ref: str = typer.Option("", "--ref", help="关联的调研目录"),
) -> None:
    """创建复盘模板."""
    from stock_master.portfolio.reviewer import create_review_template

    if not code:
        review_type = "weekly"

    path = create_review_template(
        code=code,
        review_type=review_type,
        research_ref=research_ref,
    )
    console.print(f"[bold green]复盘模板已创建：{path}[/]")
    console.print("[dim]请打开文件填写复盘内容。[/]")


@app.command()
def research(
    code: str = typer.Argument(..., help="股票代码"),
) -> None:
    """一键准备完整调研：拉数据 + 生成上下文 + 准备目录与模板."""
    from stock_master.pipeline.context_builder import build_context
    from stock_master.pipeline.orchestrator import list_agent_dimensions, prepare_research_dir
    from stock_master.data.cache import DataCache
    from stock_master.data.fetcher import fetch_stock_info

    cache = DataCache()
    info = cache.get_info(code)
    if info is None:
        info = fetch_stock_info(code)
        if "error" not in info:
            cache.set_info(code, info)
    stock_name = info.get("股票简称", info.get("名称", code))

    context_path = build_context(code, cache=cache)
    research_dir = prepare_research_dir(code, stock_name=stock_name)
    dims = list_agent_dimensions()

    console.print(f"\n[bold green]调研目录已准备就绪：{research_dir}[/]\n")
    console.print("[bold]文件结构：[/]")
    console.print(f"  📄 {context_path.name}     — 数据上下文包")
    console.print(f"  📁 agents/          — 各角色调研报告待填入")
    console.print(f"  📄 synthesis.md     — 综合研判（待生成）")
    console.print(f"  📄 decision.md      — 决策模板（待你填写）")

    console.print(f"\n[bold]可用调研维度（{len(dims)} 个）：[/]")
    for d in dims:
        console.print(f"  • {d}")

    console.print("\n[bold]下一步：[/]")
    console.print("  1. 在 Cursor 中 @ 引用 context.md + prompts/research/ 下的模板")
    console.print("  2. 分角色产出报告，保存到 agents/ 目录")
    console.print("  3. 用 prompts/synthesis/ 模板生成综合研判")
    console.print("  4. 填写 decision.md 完成决策")


if __name__ == "__main__":
    app()
