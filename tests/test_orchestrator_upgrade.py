"""研究编排升级测试."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from stock_master.pipeline.orchestrator import list_agent_dimensions, prepare_research_dir


def test_prepare_research_dir_creates_stock_report(tmp_path: Path):
    with patch("stock_master.pipeline.orchestrator.Path", side_effect=lambda *parts: tmp_path / Path(*parts)):
        research_dir = prepare_research_dir("002273", stock_name="水晶光电", research_date="2026-04-02")

    assert research_dir.exists()
    assert (research_dir / "decision.md").exists()
    assert (research_dir / "synthesis.md").exists()
    assert (research_dir / "stock-report.md").exists()


def test_list_agent_dimensions_discovers_new_prompt_files(tmp_path: Path):
    prompts_dir = tmp_path / "prompts" / "research"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "00-macro-context.md").write_text("# macro", encoding="utf-8")
    (prompts_dir / "06-capital-flow.md").write_text("# capital", encoding="utf-8")

    with patch("stock_master.pipeline.orchestrator.Path", side_effect=lambda *parts: tmp_path / Path(*parts)):
        dims = list_agent_dimensions()

    assert "macro-context" in dims
    assert "capital-flow" in dims
