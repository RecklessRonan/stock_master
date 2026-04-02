"""组合级投资建议编排 — sm suggest 的核心逻辑."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console

from stock_master.pipeline.cursor_agent import (
    SUGGEST_MODELS,
    SYNTHESIS_MODEL,
    AgentResult,
    run_agent,
)
from stock_master.portfolio.guardrails import analyze_portfolio_guardrails

console = Console()

RESEARCH_DIR = Path("research")
SUGGEST_OUTPUT_DIR = RESEARCH_DIR / "_suggest"
PORTFOLIO_PATH = Path("journal/portfolio.yaml")
CODE_PATTERN = re.compile(r"^\d{5,6}$")

MODEL_DECISION_TEMPLATE = Path("prompts/suggest/model-decision.md")
FINAL_SYNTHESIS_TEMPLATE = Path("prompts/suggest/final-synthesis.md")


@dataclass
class SuggestBundle:
    """一次 suggest 会话的输入集合."""

    codes: list[str]
    contexts: dict[str, str]  # code -> context.md 正文
    context_paths: dict[str, str]  # code -> context.md 相对路径
    portfolio_text: str
    portfolio_data: dict
    dossiers: dict[str, dict] = field(default_factory=dict)
    research_notes: dict[str, dict] = field(default_factory=dict)
    portfolio_guardrails: dict = field(default_factory=dict)
    run_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d-%H%M"))


# ---------------------------------------------------------------------------
# 1. 扫描已研究股票
# ---------------------------------------------------------------------------

def scan_researched_codes() -> list[str]:
    """扫描 research/ 顶层目录，返回合法股票代码列表."""
    if not RESEARCH_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in RESEARCH_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and CODE_PATTERN.match(d.name)
    )


# ---------------------------------------------------------------------------
# 2. 刷新 / 加载上下文
# ---------------------------------------------------------------------------

def refresh_contexts(codes: list[str]) -> dict[str, Path]:
    """对每只股票调用 build_context + prepare_research_dir，返回 {code: context_path}."""
    from stock_master.data.cache import DataCache
    from stock_master.data.fetcher import fetch_stock_info
    from stock_master.pipeline.context_builder import build_context
    from stock_master.pipeline.orchestrator import prepare_research_dir

    cache = DataCache()
    result: dict[str, Path] = {}

    for code in codes:
        console.print(f"[bold blue]刷新 {code} 上下文...[/]")
        info = cache.get_info(code)
        if info is None:
            info = fetch_stock_info(code)
            if "error" not in info:
                cache.set_info(code, info)
        stock_name = info.get("股票简称", info.get("名称", code))

        ctx_path = build_context(code, cache=cache)
        prepare_research_dir(code, stock_name=stock_name)
        result[code] = ctx_path

    return result


def load_latest_contexts(codes: list[str]) -> dict[str, Path]:
    """不刷新，直接读取每只股票最新日期目录下的 context.md."""
    result: dict[str, Path] = {}
    for code in codes:
        code_dir = RESEARCH_DIR / code
        if not code_dir.is_dir():
            continue
        date_dirs = sorted(
            (d for d in code_dir.iterdir() if d.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", d.name)),
            reverse=True,
        )
        for dd in date_dirs:
            ctx = dd / "context.md"
            if ctx.exists():
                result[code] = ctx
                break
    return result


# ---------------------------------------------------------------------------
# 3. 构建输入 bundle
# ---------------------------------------------------------------------------

def _load_portfolio() -> tuple[dict, str]:
    """返回 (portfolio_dict, portfolio_yaml_text)."""
    if not PORTFOLIO_PATH.exists():
        empty: dict = {"updated_at": date.today().isoformat(), "positions": []}
        return empty, yaml.dump(empty, allow_unicode=True, sort_keys=False)
    raw = PORTFOLIO_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {"updated_at": date.today().isoformat(), "positions": []}
    return data, raw


def _shorten_markdown(text: str, max_lines: int = 8) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def _load_research_digest(context_path: Path) -> tuple[dict, dict]:
    research_dir = context_path.parent
    dossier_path = research_dir / "dossier.yaml"
    synthesis_path = research_dir / "synthesis.md"
    agents_dir = research_dir / "agents"

    dossier = {}
    if dossier_path.exists():
        dossier = yaml.safe_load(dossier_path.read_text(encoding="utf-8")) or {}

    agents: dict[str, str] = {}
    if agents_dir.exists():
        for path in sorted(agents_dir.glob("*.md")):
            agents[path.stem] = _shorten_markdown(path.read_text(encoding="utf-8"))

    synthesis = ""
    if synthesis_path.exists():
        synthesis = _shorten_markdown(synthesis_path.read_text(encoding="utf-8"))

    return dossier, {"agents": agents, "synthesis": synthesis}


def build_inputs_bundle(
    codes: list[str],
    context_paths: dict[str, Path],
) -> SuggestBundle:
    """把持仓 + 各股上下文组装为 SuggestBundle."""
    portfolio_data, portfolio_text = _load_portfolio()

    contexts: dict[str, str] = {}
    rel_paths: dict[str, str] = {}
    dossiers: dict[str, dict] = {}
    research_notes: dict[str, dict] = {}
    for code in codes:
        p = context_paths.get(code)
        if p and p.exists():
            contexts[code] = p.read_text(encoding="utf-8")
            rel_paths[code] = str(p)
            dossier, digest = _load_research_digest(p)
            if dossier:
                dossiers[code] = dossier
            if digest["agents"] or digest["synthesis"]:
                research_notes[code] = digest

    return SuggestBundle(
        codes=codes,
        contexts=contexts,
        context_paths=rel_paths,
        dossiers=dossiers,
        research_notes=research_notes,
        portfolio_text=portfolio_text,
        portfolio_data=portfolio_data,
        portfolio_guardrails=analyze_portfolio_guardrails(portfolio_data),
    )


# ---------------------------------------------------------------------------
# 4. Prompt 构建
# ---------------------------------------------------------------------------

def _read_template(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _build_model_prompt(bundle: SuggestBundle) -> str:
    """构建发给每个模型的分析 prompt."""
    template = _read_template(MODEL_DECISION_TEMPLATE)
    parts = [template] if template else [
        "你是一位资深投资顾问。基于以下研究数据和持仓状况，给出具体的投资操作建议。\n"
    ]

    parts.append("\n## 当前持仓\n")
    parts.append(f"```yaml\n{bundle.portfolio_text}```\n")

    parts.append("\n## 组合风控约束\n")
    parts.append(
        f"```yaml\n{yaml.dump(bundle.portfolio_guardrails, allow_unicode=True, sort_keys=False)}```\n"
    )

    parts.append("\n## 研究标的上下文\n")
    for code in bundle.codes:
        ctx = bundle.contexts.get(code, "（无上下文）")
        parts.append(f"### {code}\n")
        parts.append(ctx)
        parts.append("\n")

        dossier = bundle.dossiers.get(code)
        if dossier:
            parts.append("#### 结构化 Dossier\n")
            parts.append(f"```yaml\n{yaml.dump(dossier, allow_unicode=True, sort_keys=False)}```\n")

        research_digest = bundle.research_notes.get(code, {})
        if research_digest:
            parts.append("#### 分角色研究摘录\n")
            for role, excerpt in research_digest.get("agents", {}).items():
                parts.append(f"- {role}: {excerpt}")
            synthesis = research_digest.get("synthesis")
            if synthesis:
                parts.append("\n#### 综合研判摘录\n")
                parts.append(synthesis)
                parts.append("\n")

    parts.append(
        "\n## 要求\n"
        "1. 对每只研究标的给出明确建议：强买入/买入/持有/减持/卖出/回避\n"
        "2. 建议仓位比例（占总资金百分比）\n"
        "3. 入场/出场价位建议\n"
        "4. 风险提示与止损位\n"
        "5. 必须综合考虑持仓集中度和风险敞口\n"
        "6. 是否与当前持仓冲突\n"
        "7. 若证据不足，请明确说明还缺什么，不要脑补\n"
    )
    return "\n".join(parts)


def _build_synthesis_prompt(
    bundle: SuggestBundle,
    raw_results: list[AgentResult],
) -> str:
    """构建最终综合 prompt，输入为 3 份独立建议."""
    template = _read_template(FINAL_SYNTHESIS_TEMPLATE)
    parts = [template] if template else [
        "你是一位首席投资策略师。以下是三位独立分析师基于相同数据给出的投资建议。\n"
        "请综合分析，输出最终候选决策。\n"
    ]

    parts.append("\n## 当前持仓\n")
    parts.append(f"```yaml\n{bundle.portfolio_text}```\n")

    parts.append("\n## 组合风控约束\n")
    parts.append(
        f"```yaml\n{yaml.dump(bundle.portfolio_guardrails, allow_unicode=True, sort_keys=False)}```\n"
    )

    for r in raw_results:
        if r.success:
            parts.append(f"\n## {r.display_name} 的建议\n")
            parts.append(r.output)
            parts.append("\n")

    parts.append(
        "\n## 要求\n"
        "1. 提取三位分析师的共识点\n"
        "2. 列出关键分歧点\n"
        "3. 给出最终建议排序（按优先级）\n"
        "4. 组合层面最合理的行动清单\n"
        "5. 明确声明：这是候选决策，最终由人类拍板\n"
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 5. 并行调用模型
# ---------------------------------------------------------------------------

def run_model_suggestions(
    bundle: SuggestBundle,
    timeout: Optional[int] = None,
) -> list[AgentResult]:
    """并行调用三个模型，返回各自结果."""
    prompt = _build_model_prompt(bundle)
    results: list[AgentResult] = []

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(run_agent, prompt, mid, mname, timeout): (mid, mname)
            for mid, mname in SUGGEST_MODELS
        }
        for future in as_completed(futures):
            mid, mname = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = AgentResult(
                    model_id=mid,
                    display_name=mname,
                    error=str(exc),
                    success=False,
                    returncode=-1,
                )
            results.append(result)
            status = "[bold green]完成[/]" if result.success else "[bold red]失败[/]"
            console.print(f"  {mname}: {status}（{result.elapsed_s:.1f}s）")
            if not result.success and result.error:
                console.print(f"    [dim red]↳ {result.error[:200]}[/]")

    return results


def run_final_synthesis(
    bundle: SuggestBundle,
    raw_results: list[AgentResult],
    timeout: Optional[int] = None,
) -> AgentResult:
    """使用 gpt-5.4-xhigh 汇总三份建议."""
    successful = [r for r in raw_results if r.success]
    if not successful:
        return AgentResult(
            model_id=SYNTHESIS_MODEL[0],
            display_name=SYNTHESIS_MODEL[1],
            error="所有模型均调用失败，无法生成综合报告",
            success=False,
            returncode=-1,
        )

    prompt = _build_synthesis_prompt(bundle, raw_results)
    console.print(f"[bold blue]正在生成最终综合报告（{SYNTHESIS_MODEL[1]}）...[/]")
    result = run_agent(prompt, SYNTHESIS_MODEL[0], f"Final Synthesis ({SYNTHESIS_MODEL[1]})", timeout)
    status = "[bold green]完成[/]" if result.success else "[bold red]失败[/]"
    console.print(f"  综合报告: {status}（{result.elapsed_s:.1f}s）")
    return result


# ---------------------------------------------------------------------------
# 6. 产物落盘
# ---------------------------------------------------------------------------

def save_suggest_artifacts(
    bundle: SuggestBundle,
    prompt_text: str,
    raw_results: list[AgentResult],
    synthesis_result: AgentResult,
) -> Path:
    """把本次 suggest 的全部产物写入 research/_suggest/<date>/."""
    output_dir = SUGGEST_OUTPUT_DIR / bundle.run_date
    output_dir.mkdir(parents=True, exist_ok=True)

    # inputs.md — 存档发送给模型的完整 prompt
    (output_dir / "inputs.md").write_text(prompt_text, encoding="utf-8")

    # 每个模型的原始输出
    for r in raw_results:
        fname = f"{r.model_id}.md"
        if r.success:
            header = (
                f"# 投资建议：{r.display_name}\n\n"
                f"> 生成时间：{bundle.run_date}\n"
                f"> 模型：{r.model_id}\n"
                f"> 分析标的：{', '.join(bundle.codes)}\n"
                f"> 耗时：{r.elapsed_s}s\n\n"
            )
            (output_dir / fname).write_text(header + r.output, encoding="utf-8")
        else:
            error_content = (
                f"# 调用失败：{r.display_name}\n\n"
                f"> 模型：{r.model_id}\n"
                f"> 错误：{r.error}\n"
                f"> 返回码：{r.returncode}\n"
                f"> 耗时：{r.elapsed_s}s\n"
            )
            if r.output:
                error_content += f"\n## 部分输出\n\n{r.output}\n"
            (output_dir / fname).write_text(error_content, encoding="utf-8")

    # 最终综合报告
    synth_fname = f"final-{SYNTHESIS_MODEL[0]}.md"
    if synthesis_result.success:
        header = (
            f"# 综合投资建议\n\n"
            f"> 生成时间：{bundle.run_date}\n"
            f"> 综合模型：{SYNTHESIS_MODEL[0]}\n"
            f"> 分析标的：{', '.join(bundle.codes)}\n"
            f"> 耗时：{synthesis_result.elapsed_s}s\n\n"
        )
        (output_dir / synth_fname).write_text(header + synthesis_result.output, encoding="utf-8")
    else:
        (output_dir / synth_fname).write_text(
            f"# 综合报告生成失败\n\n> 错误：{synthesis_result.error}\n",
            encoding="utf-8",
        )

    # manifest.yaml — 元数据
    manifest = {
        "run_date": bundle.run_date,
        "codes": bundle.codes,
        "context_refs": bundle.context_paths,
        "portfolio_snapshot": str(PORTFOLIO_PATH),
        "models": [
            {
                "model_id": r.model_id,
                "display_name": r.display_name,
                "success": r.success,
                "elapsed_s": r.elapsed_s,
                "output_file": f"{r.model_id}.md",
                "error": r.error if not r.success else None,
            }
            for r in raw_results
        ],
        "synthesis": {
            "model_id": synthesis_result.model_id,
            "success": synthesis_result.success,
            "elapsed_s": synthesis_result.elapsed_s,
            "output_file": synth_fname,
            "error": synthesis_result.error if not synthesis_result.success else None,
        },
    }
    (output_dir / "manifest.yaml").write_text(
        yaml.dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    return output_dir


# ---------------------------------------------------------------------------
# 7. 主编排入口
# ---------------------------------------------------------------------------

def run_suggest(
    no_refresh: bool = False,
    codes_filter: Optional[list[str]] = None,
    timeout: Optional[int] = None,
) -> Path:
    """sm suggest 的完整编排流程，返回产物输出目录."""
    # 1. 发现股票代码
    all_codes = scan_researched_codes()
    if codes_filter:
        codes = [c for c in codes_filter if c in all_codes or (RESEARCH_DIR / c).is_dir()]
        if not codes:
            raise RuntimeError(f"指定的股票代码在 research/ 中未找到：{codes_filter}")
    else:
        codes = all_codes

    if not codes:
        raise RuntimeError("research/ 目录下未发现任何已研究股票。请先运行 sm research <code>。")

    console.print(f"\n[bold]纳入分析的股票（{len(codes)} 只）：[/] {', '.join(codes)}\n")

    # 2. 刷新或加载上下文
    if no_refresh:
        console.print("[dim]跳过数据刷新，使用现有上下文。[/]\n")
        context_paths = load_latest_contexts(codes)
    else:
        context_paths = refresh_contexts(codes)

    missing = [c for c in codes if c not in context_paths]
    if missing:
        console.print(f"[bold yellow]以下股票缺少 context.md，将跳过：{missing}[/]")
        codes = [c for c in codes if c in context_paths]

    # 3. 构建 bundle
    bundle = build_inputs_bundle(codes, context_paths)
    prompt_text = _build_model_prompt(bundle)

    # 4. 并行调用三模型
    console.print("[bold]正在调用三个模型生成独立建议...[/]\n")
    raw_results = run_model_suggestions(bundle, timeout=timeout)

    # 5. 最终综合
    console.print()
    synthesis_result = run_final_synthesis(bundle, raw_results, timeout=timeout)

    # 6. 落盘
    console.print()
    output_dir = save_suggest_artifacts(bundle, prompt_text, raw_results, synthesis_result)
    console.print(f"\n[bold green]建议产物已保存到：{output_dir}[/]\n")

    return output_dir
