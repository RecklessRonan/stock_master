"""suggest 编排模块单元测试."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

from stock_master.pipeline.cursor_agent import AgentResult
from stock_master.pipeline.suggest import (
    scan_researched_codes,
    load_latest_contexts,
    build_inputs_bundle,
    save_suggest_artifacts,
    SuggestBundle,
    SUGGEST_OUTPUT_DIR,
)


class TestScanResearchedCodes:
    def test_ignores_underscore_dirs(self, tmp_path):
        (tmp_path / "002273").mkdir()
        (tmp_path / "09988").mkdir()
        (tmp_path / "_suggest").mkdir()
        (tmp_path / "__pycache__").mkdir()

        with patch("stock_master.pipeline.suggest.RESEARCH_DIR", tmp_path):
            codes = scan_researched_codes()

        assert "_suggest" not in codes
        assert "__pycache__" not in codes
        assert "002273" in codes
        assert "09988" in codes

    def test_ignores_non_numeric_dirs(self, tmp_path):
        (tmp_path / "002273").mkdir()
        (tmp_path / "notes").mkdir()
        (tmp_path / "README.md").touch()

        with patch("stock_master.pipeline.suggest.RESEARCH_DIR", tmp_path):
            codes = scan_researched_codes()

        assert codes == ["002273"]

    def test_empty_research(self, tmp_path):
        with patch("stock_master.pipeline.suggest.RESEARCH_DIR", tmp_path / "nonexistent"):
            codes = scan_researched_codes()
        assert codes == []


class TestLoadLatestContexts:
    def test_picks_latest_date(self, tmp_path):
        code_dir = tmp_path / "002273"
        (code_dir / "2026-03-28").mkdir(parents=True)
        (code_dir / "2026-03-28" / "context.md").write_text("old", encoding="utf-8")
        (code_dir / "2026-03-30").mkdir(parents=True)
        (code_dir / "2026-03-30" / "context.md").write_text("new", encoding="utf-8")

        with patch("stock_master.pipeline.suggest.RESEARCH_DIR", tmp_path):
            result = load_latest_contexts(["002273"])

        assert result["002273"].name == "context.md"
        assert "2026-03-30" in str(result["002273"])

    def test_missing_code(self, tmp_path):
        with patch("stock_master.pipeline.suggest.RESEARCH_DIR", tmp_path):
            result = load_latest_contexts(["999999"])
        assert result == {}


class TestBuildInputsBundle:
    def test_bundle_structure(self, tmp_path):
        ctx_file = tmp_path / "context.md"
        ctx_file.write_text("# 研究上下文：测试", encoding="utf-8")

        portfolio_file = tmp_path / "portfolio.yaml"
        portfolio_file.write_text(
            yaml.dump({"updated_at": "2026-03-30", "positions": []}, allow_unicode=True),
            encoding="utf-8",
        )

        with patch("stock_master.pipeline.suggest.PORTFOLIO_PATH", portfolio_file):
            bundle = build_inputs_bundle(["002273"], {"002273": ctx_file})

        assert bundle.codes == ["002273"]
        assert "研究上下文" in bundle.contexts["002273"]
        assert bundle.portfolio_data["positions"] == []


class TestSaveArtifacts:
    def test_creates_all_files(self, tmp_path):
        output_base = tmp_path / "_suggest"

        bundle = SuggestBundle(
            codes=["002273"],
            contexts={"002273": "test"},
            context_paths={"002273": "research/002273/2026-03-30/context.md"},
            portfolio_text="positions: []",
            portfolio_data={"positions": []},
            run_date="2026-03-30",
        )

        raw_results = [
            AgentResult(
                model_id="gpt-5.4-xhigh",
                display_name="GPT-5.4 Extra High",
                output="买入建议",
                success=True,
                elapsed_s=10.5,
            ),
            AgentResult(
                model_id="claude-4.6-opus-high-thinking",
                display_name="Opus 4.6 Thinking",
                output="持有建议",
                success=True,
                elapsed_s=12.3,
            ),
            AgentResult(
                model_id="gemini-3.1-pro",
                display_name="Gemini 3.1 Pro",
                error="timeout",
                success=False,
                returncode=-1,
                elapsed_s=60.0,
            ),
        ]

        synthesis = AgentResult(
            model_id="gpt-5.4-xhigh",
            display_name="Final Synthesis (GPT-5.4 Extra High)",
            output="综合建议内容",
            success=True,
            elapsed_s=15.0,
        )

        with patch("stock_master.pipeline.suggest.SUGGEST_OUTPUT_DIR", output_base):
            out_dir = save_suggest_artifacts(bundle, "prompt text", raw_results, synthesis)

        assert (out_dir / "manifest.yaml").exists()
        assert (out_dir / "inputs.md").exists()
        assert (out_dir / "gpt-5.4-xhigh.md").exists()
        assert (out_dir / "claude-4.6-opus-high-thinking.md").exists()
        assert (out_dir / "gemini-3.1-pro.md").exists()
        assert (out_dir / "final-gpt-5.4-xhigh.md").exists()

        manifest = yaml.safe_load((out_dir / "manifest.yaml").read_text(encoding="utf-8"))
        assert manifest["codes"] == ["002273"]
        assert len(manifest["models"]) == 3

        failed_model = next(m for m in manifest["models"] if m["model_id"] == "gemini-3.1-pro")
        assert failed_model["success"] is False

        gemini_content = (out_dir / "gemini-3.1-pro.md").read_text(encoding="utf-8")
        assert "失败" in gemini_content
