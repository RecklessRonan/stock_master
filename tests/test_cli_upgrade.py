"""升级版 CLI 命令测试."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from stock_master.cli import _is_research_date_dir_name, app

runner = CliRunner()


def test_dossier_command_reports_context_and_dossier_paths(tmp_path: Path):
    context_path = tmp_path / "context.md"
    context_path.write_text("# context", encoding="utf-8")
    (tmp_path / "dossier.yaml").write_text("code: '002273'\n", encoding="utf-8")

    with patch("stock_master.pipeline.context_builder.build_context", return_value=context_path):
        result = runner.invoke(app, ["dossier", "002273"])

    assert result.exit_code == 0
    assert "context.md" in result.output
    assert "dossier.yaml" in result.output


def test_check_buy_command_reads_dossier_and_prints_guardrail_result(tmp_path: Path):
    context_path = tmp_path / "context.md"
    context_path.write_text("# context", encoding="utf-8")
    (tmp_path / "dossier.yaml").write_text(
        yaml.dump(
            {
                "code": "002273",
                "rookie_action": {"verdict": "观察买点", "max_position_pct": 8.0},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with (
        patch("stock_master.pipeline.context_builder.build_context", return_value=context_path),
        patch(
            "stock_master.portfolio.trade_log.load_portfolio",
            return_value={
                "positions": [
                    {"code": "600000", "shares": 3000, "avg_cost": 10.0, "current_price": 10.0},
                    {"code": "000001", "shares": 3000, "avg_cost": 10.0, "current_price": 10.0},
                ]
            },
        ),
    ):
        result = runner.invoke(app, ["check-buy", "002273", "--position-pct", "18"])

    assert result.exit_code == 0
    assert "谨慎" in result.output
    assert "观察买点" in result.output


def test_is_research_date_dir_name_requires_strict_iso_date():
    assert _is_research_date_dir_name("2026-04-02") is True
    assert _is_research_date_dir_name("abcd-ef-gh") is False
    assert _is_research_date_dir_name("2026-4-02") is False
