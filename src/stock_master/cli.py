"""Stock Master CLI 入口."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import re
import typer
import yaml
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="sm",
    help="Stock Master — 本地优先的个人股票投资决策系统",
    no_args_is_help=True,
)
console = Console()

RESEARCH_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_analysis_payload(code: str) -> dict:
    from stock_master.data.cache import DataCache
    from stock_master.data.fetcher import (
        fetch_daily_kline,
        fetch_financial_summary,
        fetch_news,
        fetch_stock_info,
        fetch_valuation,
        fetch_valuation_history,
    )
    from stock_master.data.indicators import add_all_indicators

    cache = DataCache()

    info = cache.get_info(code)
    if info is None:
        info = fetch_stock_info(code)
        if "error" not in info:
            cache.set_info(code, info)

    kline = cache.get_kline(code)
    if kline is None:
        kline = fetch_daily_kline(code)
        if not kline.empty:
            cache.set_kline(code, kline)
    if not kline.empty:
        kline = add_all_indicators(kline)

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

    financial = fetch_financial_summary(code)
    news = fetch_news(code)
    return {
        "info": info,
        "kline": kline,
        "valuation": valuation,
        "valuation_history": valuation_history,
        "financial": financial,
        "news": news,
    }


def _display_factor_value(result, factor_name: str) -> tuple[str, str]:
    factor = result.factors.get(factor_name)
    if factor is not None and factor.status == "missing":
        return "N/A", "▒" * 10
    value = result.to_dict()[factor_name]
    bar = "█" * int(value / 10) + "░" * (10 - int(value / 10))
    return f"{value:.1f}", bar


def _is_research_date_dir_name(name: str) -> bool:
    return bool(RESEARCH_DATE_PATTERN.match(name))


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
    console.print(f"[bold]Dossier 文件：[/] {path.parent / 'dossier.yaml'}")
    console.print("[dim]接下来可在 Cursor 中 @ 引用 context.md、dossier.yaml 与 prompts/ 模板开始调研。[/]")


@app.command()
def dossier(
    code: str = typer.Argument(..., help="股票代码，如 002273"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="指定输出目录"),
) -> None:
    """生成结构化个股 dossier."""
    from stock_master.pipeline.context_builder import build_context

    output_dir = Path(output) if output else None
    context_path = build_context(code, output_dir=output_dir)
    dossier_path = context_path.parent / "dossier.yaml"
    console.print(f"\n[bold]上下文文件：[/] {context_path}")
    console.print(f"[bold]Dossier 文件：[/] {dossier_path}")
    console.print("[dim]建议优先阅读 dossier.yaml 里的新手行动建议与证据覆盖度。[/]")


@app.command()
def score(
    code: str = typer.Argument(..., help="股票代码"),
) -> None:
    """查看股票的升级版多因子评分."""
    from stock_master.analysis.quantitative import compute_score
    payload = _load_analysis_payload(code)
    info = payload["info"]
    stock_name = info.get("股票简称", info.get("名称", code))
    result = compute_score(
        payload["kline"],
        payload["valuation"],
        financial=payload["financial"],
        valuation_history=payload["valuation_history"],
        news=payload["news"],
    )

    table = Table(title=f"{stock_name} ({code}) 多因子评分")
    table.add_column("维度", style="cyan")
    table.add_column("评分", justify="right", style="bold")
    table.add_column("图示", style="green")

    for dim, val in result.to_dict().items():
        display_value, bar = _display_factor_value(result, dim) if dim in result.factors else (
            f"{val:.1f}",
            "█" * int(val / 10) + "░" * (10 - int(val / 10)),
        )
        style = "bold red" if dim in {"综合", "可信度"} else ""
        table.add_row(dim, display_value, bar, style=style)

    console.print(table)


@app.command()
def compare(
    codes: list[str] = typer.Argument(..., help="要对比的股票代码列表"),
) -> None:
    """多股对比升级版因子评分."""
    from stock_master.analysis.quantitative import compute_score

    table = Table(title="多股对比")
    table.add_column("股票", style="cyan")
    table.add_column("质量", justify="right")
    table.add_column("估值", justify="right")
    table.add_column("趋势", justify="right")
    table.add_column("风险", justify="right")
    table.add_column("催化剂", justify="right")
    table.add_column("综合", justify="right", style="bold")
    table.add_column("可信度", justify="right")

    for code in codes:
        payload = _load_analysis_payload(code)
        info = payload["info"]
        name = info.get("股票简称", info.get("名称", code))
        s = compute_score(
            payload["kline"],
            payload["valuation"],
            financial=payload["financial"],
            valuation_history=payload["valuation_history"],
            news=payload["news"],
        )
        d = s.to_dict()
        quality_value, _ = _display_factor_value(s, "质量")
        value_value, _ = _display_factor_value(s, "估值")
        trend_value, _ = _display_factor_value(s, "趋势")
        risk_value, _ = _display_factor_value(s, "风险")
        catalyst_value, _ = _display_factor_value(s, "催化剂")
        table.add_row(
            f"{name}\n({code})",
            quality_value,
            value_value,
            trend_value,
            risk_value,
            catalyst_value,
            f"{d['综合']:.1f}",
            f"{d['可信度']:.1f}",
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
def check_buy(
    code: str = typer.Argument(..., help="候选股票代码"),
    position_pct: float = typer.Option(..., "--position-pct", help="计划仓位百分比"),
) -> None:
    """买入前检查：结合组合风控和 dossier 建议判断是否值得出手."""
    from stock_master.pipeline.context_builder import build_context
    from stock_master.portfolio.guardrails import evaluate_buy_candidate
    from stock_master.portfolio.trade_log import load_portfolio

    context_path = build_context(code)
    dossier_path = context_path.parent / "dossier.yaml"
    dossier = {}
    if dossier_path.exists():
        dossier = yaml.safe_load(dossier_path.read_text(encoding="utf-8")) or {}

    from stock_master.data.fetcher import fetch_daily_kline

    portfolio_data = load_portfolio()
    kline_data_dict = None
    kline = fetch_daily_kline(code)
    if not kline.empty:
        recent_high = float(kline["最高"].tail(20).max())
        current_price = float(kline["收盘"].iloc[-1])
        pct_20 = (current_price / float(kline["收盘"].iloc[-20]) - 1) * 100 if len(kline) >= 20 else 0.0
        kline_data_dict = {
            "recent_high": recent_high,
            "current_price": current_price,
            "pct_from_high": (current_price / recent_high * 100) if recent_high > 0 else 0.0,
            "short_term_gain": pct_20,
        }

    result = evaluate_buy_candidate(
        portfolio_data,
        {
            "code": code,
            "name": dossier.get("stock_name", code),
            "planned_position_pct": position_pct,
        },
        kline_data=kline_data_dict,
        dossier=dossier,
    )
    rookie_action = dossier.get("rookie_action", {})
    recommended_max = rookie_action.get("max_position_pct", 0.0)

    console.print(f"[bold]买前检查：{code}[/]")
    console.print(f"- 风控结论：{result['verdict']}")
    if rookie_action:
        console.print(f"- Dossier 结论：{rookie_action.get('verdict', '观察')}")
        console.print(f"- 建议单票上限：{recommended_max:.1f}%")
    if recommended_max and position_pct > recommended_max:
        console.print(f"- [yellow]计划仓位高于 dossier 建议上限：{position_pct:.1f}% > {recommended_max:.1f}%[/]")
    if result["warnings"]:
        console.print("- 风险提示：")
        for warning in result["warnings"]:
            console.print(f"  - {warning}")
    else:
        console.print("- 当前未发现明显组合风控冲突。")


@app.command()
def watchlist(
    action: str = typer.Option("list", "--action", help="list/add/remove"),
    code: str = typer.Option("", "--code", help="股票代码"),
    bucket: str = typer.Option("ready", "--bucket", help="ready/wait_price/avoid"),
    target_price: Optional[float] = typer.Option(None, "--target-price", help="目标观察价"),
    thesis: str = typer.Option("", "--thesis", help="观察逻辑"),
) -> None:
    """管理观察清单，并生成简易提醒."""
    from stock_master.data.fetcher import fetch_daily_kline, fetch_stock_info
    from stock_master.portfolio.trade_log import load_watchlist, save_watchlist
    from stock_master.portfolio.watchlist import generate_watchlist_alerts, upsert_watchlist_item

    data = load_watchlist()

    if action == "add":
        if not code:
            console.print("[bold red]添加观察清单时必须提供 --code[/]")
            raise typer.Exit(1)
        info = fetch_stock_info(code)
        stock_name = info.get("股票简称", info.get("名称", code))
        updated = upsert_watchlist_item(
            data,
            code=code,
            name=stock_name,
            bucket=bucket,
            target_price=target_price,
            thesis=thesis,
        )
        save_watchlist(updated)
        console.print(f"[bold green]已加入观察清单：{stock_name} ({code})[/]")
        return

    if action == "remove":
        data["stocks"] = [item for item in data.get("stocks", []) if item.get("code") != code]
        save_watchlist(data)
        console.print(f"[bold green]已移除观察清单：{code}[/]")
        return

    stocks = data.get("stocks", [])
    if not stocks:
        console.print("[dim]观察清单为空。可用 `sm watchlist --action add --code 002273` 添加。[/]")
        return

    dossiers = {}
    market_prices = {}
    for item in stocks:
        stock_code = item.get("code", "")
        research_root = Path("research") / stock_code
        if research_root.exists():
            date_dirs = sorted(
                [
                    d
                    for d in research_root.iterdir()
                    if d.is_dir() and _is_research_date_dir_name(d.name)
                ],
                reverse=True,
            )
            for date_dir in date_dirs:
                dossier_path = date_dir / "dossier.yaml"
                if dossier_path.exists():
                    dossiers[stock_code] = yaml.safe_load(dossier_path.read_text(encoding="utf-8")) or {}
                    break
        kline = fetch_daily_kline(stock_code)
        if not kline.empty:
            market_prices[stock_code] = float(kline["收盘"].iloc[-1])

    alerts = generate_watchlist_alerts(data, dossiers=dossiers, market_prices=market_prices)

    table = Table(title=f"观察清单（更新于 {data.get('updated_at', 'N/A')}）")
    table.add_column("股票", style="cyan")
    table.add_column("分组")
    table.add_column("目标价", justify="right")
    table.add_column("现价", justify="right")
    table.add_column("观察逻辑", style="dim")
    for item in stocks:
        current = market_prices.get(item.get("code", ""))
        table.add_row(
            f"{item.get('name', '')}\n({item.get('code', '')})",
            item.get("bucket", ""),
            f"{item.get('target_price', '') or '-'}",
            f"{current:.2f}" if current is not None else "-",
            item.get("thesis", ""),
        )
    console.print(table)
    if alerts:
        console.print("\n[bold]提醒：[/]")
        for alert in alerts:
            console.print(f"- {alert['message']}")


@app.command("weekly-review")
def weekly_review() -> None:
    """生成包含行为偏差提示的周复盘模板."""
    from stock_master.portfolio.learning import build_learning_report
    from stock_master.portfolio.reviewer import create_review_template
    from stock_master.portfolio.trade_log import list_trades

    reviews_dir = Path("journal/reviews")
    existing_reviews = [{"path": str(p)} for p in reviews_dir.glob("*.md")] if reviews_dir.exists() else []
    report = build_learning_report(list_trades(), existing_reviews)
    path = create_review_template(code="", review_type="weekly")

    extra_lines = [
        "## 行为偏差提示",
        "",
    ]
    if report["bias_flags"]:
        extra_lines.extend(f"- {item}" for item in report["bias_flags"])
    else:
        extra_lines.append("- 本周未发现明显行为偏差。")
    extra_lines.extend([
        "",
        "## 下周执行清单",
        "",
    ])
    extra_lines.extend(f"- {item}" for item in report["recommendations"])
    extra_block = "\n".join(extra_lines) + "\n"
    current = path.read_text(encoding="utf-8")
    marker = "## 行为偏差提示"
    if marker in current:
        current = current.split(marker, 1)[0].rstrip() + "\n\n" + extra_block
        path.write_text(current, encoding="utf-8")
    else:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n" + extra_block)

    console.print(f"[bold green]周复盘模板已创建：{path}[/]")


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
工作区根目录即当前仓库。**你必须先通过工具读取下面绝对路径的图像文件**（PNG/JPG 等），
逐字逐字段从截图里识别数字与文字；**禁止**仅凭 journal/portfolio.yaml、对话记忆或常识臆造持仓数据。
若无法读取该文件，先说明原因并中止。

截图文件（绝对路径）：{image_abs}

完成以下操作：

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
        console.print(
            f"[bold]发现 {len(pending)} 张待处理截图[/] "
            "[dim]（按修改时间从新到旧依次处理；若只要最新一张，请先移走或归档其它待处理文件）[/]"
        )
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
    """未归档截图；按 mtime 降序（优先处理最新放入的一张）。"""
    candidates = [
        f
        for f in snapshots_dir.iterdir()
        if f.suffix.lower() in IMAGE_SUFFIXES and not _is_archived(f.stem)
    ]
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)


def _process_snapshot(image_path: Path, snapshots_dir: Path, no_ai: bool, note: str) -> None:
    import subprocess

    from stock_master.pipeline.cursor_agent import (
        _agent_env,
        agent_cli_install_hint,
        resolve_agent_command,
    )

    if no_ai:
        console.print(f"[bold green]截图已导入：{image_path}[/]")
        console.print("[dim]跳过 AI 处理。可在 Cursor 中手动处理重命名与持仓更新。[/]")
        return

    cmd_prefix = resolve_agent_command()
    if not cmd_prefix:
        console.print("[bold yellow]未检测到 agent CLI，无法自动处理。[/]")
        console.print(f"[dim]{agent_cli_install_hint()}[/]")
        console.print(f"[dim]截图已保存在 {image_path}，请在 Cursor 中手动处理。[/]")
        return

    old_portfolio = _load_portfolio_snapshot()

    repo_root = Path.cwd().resolve()
    image_abs = str(Path(image_path).resolve())
    prompt = SNAPSHOT_PROMPT_TEMPLATE.format(
        image_abs=image_abs,
        ext=image_path.suffix.lower(),
    )
    console.print(f"[dim]截图文件：{image_path.name} → {image_abs}[/]")
    console.print("[bold]正在调用 AI 识别截图并更新持仓...[/]\n")

    result = subprocess.run(
        [
            *cmd_prefix,
            "--print",
            "--trust",
            "--force",
            "--approve-mcps",
            "--output-format",
            "text",
            "--workspace",
            str(repo_root),
            prompt,
        ],
        text=True,
        cwd=repo_root,
        env=_agent_env(),
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
        console.print(
            "[dim]若提示 Authentication / login，请执行 [bold]sm agent-login[/]，"
            "或设置环境变量 CURSOR_API_KEY 后重试。[/]"
        )


@app.command("agent-login")
def agent_login() -> None:
    """登录 Cursor Agent CLI（snapshot / suggest 等功能依赖已登录的 agent）。"""
    import subprocess

    from stock_master.pipeline.cursor_agent import _agent_env, agent_cli_install_hint, resolve_agent_command

    cmd_prefix = resolve_agent_command()
    if not cmd_prefix:
        console.print("[bold red]未找到 agent CLI。[/]")
        console.print(f"[dim]{agent_cli_install_hint()}[/]")
        raise typer.Exit(1)

    console.print(f"[dim]使用：{cmd_prefix[0]}[/]")
    raise typer.Exit(subprocess.call([*cmd_prefix, "login"], env=_agent_env()))


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
    console.print("  📄 dossier.yaml    — 结构化事实包与新手行动建议")
    console.print(f"  📁 agents/          — 各角色调研报告待填入")
    console.print("  📄 stock-report.md — 一页式结论页（8 个关键问题）")
    console.print(f"  📄 synthesis.md     — 综合研判（待生成）")
    console.print(f"  📄 decision.md      — 决策模板（待你填写）")

    console.print(f"\n[bold]可用调研维度（{len(dims)} 个）：[/]")
    for d in dims:
        console.print(f"  • {d}")

    console.print("\n[bold]下一步：[/]")
    console.print("  1. 在 Cursor 中 @ 引用 context.md + dossier.yaml + prompts/research/ 下的模板")
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


@app.command()
def alerts(
    scan: bool = typer.Option(False, "--scan", help="扫描持仓和观察清单生成新提醒"),
    acknowledge: Optional[int] = typer.Option(None, "--ack", help="确认指定序号的提醒"),
) -> None:
    """查看和管理投资提醒."""
    from stock_master.portfolio.alerts import (
        acknowledge_alert,
        format_alerts_summary,
        load_alerts,
        scan_all_alerts,
    )
    from stock_master.portfolio.trade_log import load_portfolio, load_watchlist

    if acknowledge is not None:
        acknowledge_alert(acknowledge)
        console.print(f"[bold green]提醒 #{acknowledge} 已确认。[/]")
        return

    if scan:
        from stock_master.data.fetcher import (
            fetch_capital_flow,
            fetch_daily_kline,
            fetch_valuation,
        )
        from stock_master.portfolio.alerts import save_alerts

        portfolio_data = load_portfolio()
        watchlist_data = load_watchlist()
        market_data: dict = {}

        all_codes = set()
        for pos in portfolio_data.get("positions", []):
            all_codes.add(pos.get("code", ""))
        for stock in watchlist_data.get("stocks", []):
            all_codes.add(stock.get("code", ""))

        for code in all_codes:
            if not code:
                continue
            console.print(f"[dim]扫描 {code}...[/]")
            entry: dict = {}
            kline = fetch_daily_kline(code)
            if not kline.empty:
                entry["current_price"] = float(kline["收盘"].iloc[-1])
            entry["capital_flow"] = fetch_capital_flow(code)
            entry["valuation"] = fetch_valuation(code)
            market_data[code] = entry

        new_alerts = scan_all_alerts(
            portfolio=portfolio_data,
            watchlist=watchlist_data,
            market_data=market_data,
        )
        if new_alerts:
            save_alerts(new_alerts)
            console.print(f"[bold green]发现 {len(new_alerts)} 条新提醒！[/]")
        else:
            console.print("[dim]未发现新的异动提醒。[/]")

    existing = load_alerts()
    if not existing:
        console.print("[dim]暂无提醒。使用 --scan 扫描新提醒。[/]")
        return

    table = Table(title="投资提醒")
    table.add_column("#", style="dim")
    table.add_column("类型", style="cyan")
    table.add_column("级别")
    table.add_column("股票")
    table.add_column("内容")
    table.add_column("时间", style="dim")

    for i, alert in enumerate(existing):
        severity_style = {
            "critical": "bold red",
            "warning": "yellow",
            "info": "dim",
        }.get(alert.get("severity", "info"), "")
        table.add_row(
            str(i),
            alert.get("type", ""),
            f"[{severity_style}]{alert.get('severity', '')}[/{severity_style}]",
            alert.get("code", ""),
            alert.get("message", ""),
            alert.get("created_at", "")[:16],
        )
    console.print(table)


@app.command("paper-trade")
def paper_trade(
    action: str = typer.Argument(..., help="操作：buy/sell/status/performance"),
    code: str = typer.Option("", "--code", "-c", help="股票代码"),
    price: float = typer.Option(0.0, "--price", "-p", help="价格"),
    shares: int = typer.Option(0, "--shares", "-s", help="股数"),
    reason: str = typer.Option("", "--reason", "-r", help="交易理由"),
) -> None:
    """模拟盘交易 — 不涉及真实资金."""
    from stock_master.portfolio.execution import PaperPortfolio

    paper = PaperPortfolio()

    if action == "status":
        positions = paper.get_positions()
        if not positions:
            console.print("[dim]模拟盘暂无持仓。[/]")
            return
        table = Table(title="模拟盘持仓")
        table.add_column("股票", style="cyan")
        table.add_column("股数", justify="right")
        table.add_column("成本价", justify="right")
        for pos in positions:
            table.add_row(
                f"{pos.get('name', '')}\n({pos.get('code', '')})",
                str(pos.get("shares", 0)),
                f"{pos.get('avg_cost', 0):.2f}",
            )
        console.print(table)
        return

    if action == "performance":
        perf = paper.get_performance()
        console.print("[bold]模拟盘业绩[/]")
        console.print(f"  初始资金：{perf.get('initial_cash', 0):,.2f}")
        console.print(f"  当前现金：{perf.get('current_cash', 0):,.2f}")
        console.print(f"  持仓市值：{perf.get('position_value', 0):,.2f}")
        console.print(f"  总资产：{perf.get('total_assets', 0):,.2f}")
        console.print(f"  总收益率：{perf.get('total_return_pct', 0):.2f}%")
        console.print(f"  交易次数：{perf.get('trade_count', 0)}")
        return

    if not code:
        console.print("[bold red]请指定 --code[/]")
        raise typer.Exit(1)
    if price <= 0 or shares <= 0:
        console.print("[bold red]请指定有效的 --price 和 --shares[/]")
        raise typer.Exit(1)

    from stock_master.data.fetcher import fetch_stock_info
    info = fetch_stock_info(code)
    stock_name = info.get("股票简称", info.get("名称", code))

    result = paper.execute_trade(
        code=code, name=stock_name, action=action,
        price=price, shares=shares, reason=reason,
    )
    console.print(f"[bold green]{result.get('message', '操作完成')}[/]")


@app.command()
def profile() -> None:
    """查看个人交易行为画像和学习建议."""
    from stock_master.portfolio.learning import build_trader_profile, detect_behavioral_biases
    from stock_master.portfolio.trade_log import list_trades, load_portfolio

    trades = list_trades()
    portfolio_data = load_portfolio()

    if not trades:
        console.print("[dim]暂无交易记录，无法生成画像。先使用 sm trade 记录交易。[/]")
        return

    profile_data = build_trader_profile(trades, [])
    biases = detect_behavioral_biases(trades, portfolio_data)

    console.print("[bold]📊 交易行为画像[/]\n")
    console.print(f"  总交易次数：{profile_data.get('total_trades', 0)}")
    console.print(f"  胜率：{profile_data.get('win_rate', 0):.1f}%")
    console.print(f"  平均持有天数：{profile_data.get('avg_holding_days', 0):.0f}")

    if profile_data.get("strengths"):
        console.print("\n[bold green]  优势：[/]")
        for s in profile_data["strengths"]:
            console.print(f"    ✓ {s}")

    if profile_data.get("common_mistakes"):
        console.print("\n[bold yellow]  常见错误：[/]")
        for m in profile_data["common_mistakes"]:
            console.print(f"    ✗ {m}")

    if biases:
        console.print("\n[bold red]  行为偏差检测：[/]")
        for b in biases:
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                b.get("severity", "low"), "⚪"
            )
            console.print(f"    {severity_icon} {b.get('bias_type', '')}: {b.get('description', '')}")
            console.print(f"      → {b.get('recommendation', '')}")

    if profile_data.get("recommendations"):
        console.print("\n[bold]  学习建议：[/]")
        for r in profile_data["recommendations"]:
            console.print(f"    • {r}")


if __name__ == "__main__":
    app()
