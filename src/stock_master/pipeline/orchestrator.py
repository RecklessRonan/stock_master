"""研究编排 — 为 Cursor 半自动多模型调研准备目录结构与模板."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from jinja2 import Template

DECISION_TEMPLATE = """\
# 投资决策：{{stock_name}} ({{stock_code}})

> 日期：{{date}}
> 研究引用：{{research_dir}}

## 核心判断

<!-- 请填写：强买入/买入/持有/减持/卖出/回避 -->
**判定**：

## 投资逻辑

<!-- 2-3 句话说明为什么 -->


## 计划仓位

<!-- 占总资金百分比 -->
- 仓位：%
- 入场价：
- 止损价：

## 入场触发条件

<!-- 满足什么条件才执行买入 -->
-

## 失效条件（必填）

<!-- 什么情况下放弃此论点 -->
-

## 预期持有周期


## 下次复盘日期

<!-- YYYY-MM-DD，届时需要检查什么 -->


## 信心评分

<!-- 1-10 分 -->
/10

## 备注

"""


def prepare_research_dir(
    code: str,
    stock_name: str = "",
    research_date: Optional[str] = None,
) -> Path:
    """准备调研目录结构，包含 agents 子目录和 decision 模板."""
    if research_date is None:
        research_date = date.today().isoformat()

    research_dir = Path("research") / code / research_date
    agents_dir = research_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    decision_path = research_dir / "decision.md"
    if not decision_path.exists():
        tmpl = Template(DECISION_TEMPLATE)
        content = tmpl.render(
            stock_name=stock_name or code,
            stock_code=code,
            date=research_date,
            research_dir=str(research_dir),
        )
        decision_path.write_text(content, encoding="utf-8")

    synthesis_path = research_dir / "synthesis.md"
    if not synthesis_path.exists():
        synthesis_path.write_text(
            f"# 综合研判：{stock_name or code} ({code})\\n\\n"
            f"> 日期：{research_date}\\n\\n"
            "<!-- 使用 prompts/synthesis/consensus-matrix.md 模板生成 -->\\n",
            encoding="utf-8",
        )

    return research_dir


def list_agent_dimensions() -> list[str]:
    """列出所有可用的调研维度."""
    prompts_dir = Path("prompts/research")
    if not prompts_dir.exists():
        return []
    return sorted(
        p.stem.split("-", 1)[-1] if "-" in p.stem else p.stem
        for p in prompts_dir.glob("*.md")
    )
