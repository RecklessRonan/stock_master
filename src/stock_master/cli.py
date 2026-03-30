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


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")

SNAPSHOT_PROMPT_TEMPLATE = """\
读取持仓截图 {image_path}，完成以下操作：

## 1. 重命名截图
从截图中找到「更新时间」（格式通常为 HH:MM:SS），结合今天的日期，
将文件重命名为 journal/snapshots/YYYY-MM-DD-HHmm{ext}（精确到分钟）。
如果该文件名已存在，则在末尾加 -2、-3 依此类推。

## 2. 对比持仓变化，推断交易操作
读取当前 journal/portfolio.yaml 中的持仓（即上一次快照的状态），
与截图中的新持仓做对比。按以下规则推断交易：
- 新出现的股票 → action: buy
- 消失的股票 → action: sell
- 股数增加 → action: add
- 股数减少 → action: reduce
- 完全没变 → 无操作

对于每一笔推断出的交易，需要从持仓变化反推交易价格：
- buy/sell：价格 = 新持仓的成本价（或旧持仓成本价）
- add：通过 (新均价×新总股数 - 旧均价×旧总股数) / 新增股数 反推
- reduce：价格 ≈ 截图中的现价（近似值）

## 3. 写入交易记录
对每笔推断出的交易，创建两个文件（严格遵循现有格式）：

**journal/trades/YYYY-MM-DD-CODE-ACTION.yaml**（如果文件名已存在则加 -1、-2...）:
```yaml
date: 'YYYY-MM-DD'
code: 'CODE'
name: 股票名称
action: buy/sell/add/reduce
price: 成交价格
shares: 成交股数
amount: price × shares
reason: '持仓截图自动推断'
research_ref: ''
confidence: 5
tags: [auto-detected]
review_date: ''
created_at: 'ISO格式时间'
```

**journal/entries/YYYY-MM-DD-ACTION-CODE.md**:
```markdown
# 交易记录：ACTION 股票名称 (CODE)

> 日期：YYYY-MM-DD
> 操作：action 股数 股 @ 价格
> 金额：总额

> 来源：持仓截图自动识别

## 决策逻辑

<!-- 待补充 -->

## 当时情绪

<!-- 交易时的心理状态与信心水平 -->


## AI 建议摘要

<!-- 各模型当时给出的关键意见 -->


## 备注

```

## 4. 更新持仓
读取截图中的完整持仓数据（账户资产、总市值、可用资金、仓位比例、
每只股票的代码/名称/持仓股数/成本/现价/浮动盈亏等），
更新 journal/portfolio.yaml，格式与现有文件保持一致。
snapshot 字段指向重命名后的文件路径。

## 输出要求
完成后打印一个简洁摘要，说明：
- 截图重命名为什么
- 检测到几笔交易，分别是什么
- portfolio.yaml 更新了哪些字段
如果没有检测到交易变化，说明"持仓无变化"即可。
"""


@app.command()
def snapshot(
    image: Optional[str] = typer.Argument(None, help="截图文件路径（留空则处理 snapshots/ 内未归档截图）"),
    no_ai: bool = typer.Option(False, "--no-ai", help="跳过 AI 处理，仅导入文件"),
    note: str = typer.Option("", "--note", "-n", help="备注（写入同名 .txt）"),
    list_all: bool = typer.Option(False, "--list", "-l", help="查看截图列表"),
) -> None:
    """导入持仓截图并自动识别、更新持仓（需要 Cursor agent CLI）."""
    import shutil
    import subprocess
    from datetime import datetime

    snapshots_dir = Path("journal/snapshots")
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    if list_all:
        _list_snapshots(snapshots_dir)
        return

    if image is None:
        pending = _find_pending_snapshots(snapshots_dir)
        if not pending:
            _list_snapshots(snapshots_dir)
            return
        console.print(f"[bold]发现 {len(pending)} 张待处理截图[/]")
        for p in pending:
            _process_snapshot(p, snapshots_dir, no_ai, note)
        return

    src = Path(image)
    if not src.exists():
        console.print(f"[bold red]文件不存在：{src}[/]")
        raise typer.Exit(1)

    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    ext = src.suffix.lower() or ".png"
    dest = snapshots_dir / f"_pending_{ts}{ext}"
    shutil.copy2(src, dest)
    console.print(f"[dim]截图已复制到 {dest}[/]")

    _process_snapshot(dest, snapshots_dir, no_ai, note)


def _is_archived(name: str) -> bool:
    """已归档的截图文件名格式：YYYY-MM-DD-HHmm 或 YYYY-MM-DD-HHmm-N."""
    import re

    return bool(re.match(r"^\d{4}-\d{2}-\d{2}-\d{4}(-\d+)?$", name))


def _list_snapshots(snapshots_dir: Path) -> None:
    files = sorted(
        [f for f in snapshots_dir.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES and _is_archived(f.stem)],
        reverse=True,
    )
    if not files:
        console.print("[dim]暂无持仓截图。用法：sm snapshot <图片路径>[/]")
        return

    table = Table(title="持仓截图记录")
    table.add_column("日期", style="cyan")
    table.add_column("文件", style="dim")
    table.add_column("大小", justify="right")
    table.add_column("备注", style="yellow")

    for f in files:
        size_kb = f.stat().st_size / 1024
        note_file = f.with_suffix(".txt")
        file_note = note_file.read_text().strip() if note_file.exists() else ""
        table.add_row(f.stem, f.name, f"{size_kb:.0f} KB", file_note)

    console.print(table)


def _find_pending_snapshots(snapshots_dir: Path) -> list[Path]:
    return sorted(
        f for f in snapshots_dir.iterdir()
        if f.suffix.lower() in IMAGE_SUFFIXES and not _is_archived(f.stem)
    )


def _process_snapshot(image_path: Path, snapshots_dir: Path, no_ai: bool, note: str) -> None:
    import shutil
    import subprocess

    if no_ai:
        console.print(f"[bold green]截图已导入：{image_path}[/]")
        console.print("[dim]跳过 AI 处理。可在 Cursor 中手动处理重命名与持仓更新。[/]")
        return

    if not shutil.which("agent"):
        console.print("[bold yellow]未检测到 agent CLI，无法自动处理。[/]")
        console.print("[dim]安装方法：curl https://cursor.com/install -fsS | bash[/]")
        console.print(f"[dim]截图已保存在 {image_path}，请在 Cursor 中手动处理。[/]")
        return

    old_portfolio = _load_portfolio_snapshot()

    prompt = SNAPSHOT_PROMPT_TEMPLATE.format(image_path=image_path, ext=image_path.suffix.lower())
    console.print("[bold]正在调用 AI 识别截图并更新持仓...[/]\n")

    result = subprocess.run(
        ["agent", "-p", "--trust", "--force", "--approve-mcps", prompt],
        text=True,
    )

    console.print()
    if result.returncode == 0:
        console.print("[bold green]处理完成！[/]")
        new_portfolio = _load_portfolio_snapshot()
        _print_portfolio_diff(old_portfolio, new_portfolio)
        if note:
            renamed = _find_latest_snapshot(snapshots_dir)
            if renamed:
                renamed.with_suffix(".txt").write_text(note + "\n")
                console.print(f"  备注已保存：{renamed.with_suffix('.txt')}")
    else:
        console.print(f"[bold red]AI 处理出错（exit {result.returncode}）[/]")


def _load_portfolio_snapshot() -> dict:
    import yaml

    portfolio_path = Path("journal/portfolio.yaml")
    if not portfolio_path.exists():
        return {"positions": []}
    with open(portfolio_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"positions": []}


def _print_portfolio_diff(old: dict, new: dict) -> None:
    old_pos = {p["code"]: p for p in old.get("positions", [])}
    new_pos = {p["code"]: p for p in new.get("positions", [])}

    all_codes = sorted(set(old_pos) | set(new_pos))
    if not all_codes:
        return

    changes = []
    for code in all_codes:
        o = old_pos.get(code)
        n = new_pos.get(code)
        if o is None and n is not None:
            changes.append(f"  [green]+[/] 买入 {n.get('name', code)}({code}) {n.get('shares', 0)} 股")
        elif o is not None and n is None:
            changes.append(f"  [red]-[/] 清仓 {o.get('name', code)}({code}) {o.get('shares', 0)} 股")
        elif o and n and o.get("shares") != n.get("shares"):
            diff = n.get("shares", 0) - o.get("shares", 0)
            action = "加仓" if diff > 0 else "减仓"
            changes.append(f"  [yellow]~[/] {action} {n.get('name', code)}({code}) {abs(diff)} 股")

    if changes:
        console.print("\n[bold]持仓变动：[/]")
        for c in changes:
            console.print(c)
        console.print()
    else:
        console.print("\n[dim]持仓无变化。[/]\n")


def _find_latest_snapshot(snapshots_dir: Path) -> Path | None:
    files = sorted(
        (f for f in snapshots_dir.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES and not f.stem.startswith("_pending_")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


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


@app.command()
def suggest(
    no_refresh: bool = typer.Option(False, "--no-refresh", help="跳过数据刷新，使用现有上下文"),
    codes: Optional[list[str]] = typer.Option(None, "--code", "-c", help="仅分析指定股票（可多次使用）"),
) -> None:
    """多模型智能投资建议 — 调用 GPT/Claude/Gemini 生成综合决策."""
    import shutil

    from stock_master.pipeline.cursor_agent import ensure_agent_available
    from stock_master.pipeline.suggest import run_suggest

    try:
        ensure_agent_available()
    except RuntimeError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(1) from None

    try:
        output_dir = run_suggest(
            no_refresh=no_refresh,
            codes_filter=codes or None,
        )
    except RuntimeError as exc:
        console.print(f"[bold red]错误：{exc}[/]")
        raise typer.Exit(1) from None

    console.print("[bold]产物目录结构：[/]")
    for f in sorted(output_dir.iterdir()):
        console.print(f"  📄 {f.name}")
    console.print("\n[dim]这是候选决策，最终由你人工拍板。[/]")


if __name__ == "__main__":
    app()
