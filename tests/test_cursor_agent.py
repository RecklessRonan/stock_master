"""cursor_agent 模块单元测试."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from stock_master.pipeline.cursor_agent import (
    AgentResult,
    SUGGEST_MODELS,
    ensure_agent_available,
    run_agent,
)


class TestEnsureAgentAvailable:
    def test_found(self):
        with patch("shutil.which", return_value="/usr/local/bin/agent"):
            assert ensure_agent_available() == "/usr/local/bin/agent"

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="未检测到 agent CLI"):
                ensure_agent_available()


class TestRunAgent:
    def test_success(self):
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "建议买入"
        fake_proc.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/local/bin/agent"),
            patch("subprocess.run", return_value=fake_proc) as mock_run,
        ):
            result = run_agent("测试 prompt", "gpt-5.4-xhigh", "GPT-5.4 Extra High")

        assert result.success is True
        assert result.output == "建议买入"
        assert result.model_id == "gpt-5.4-xhigh"
        assert result.elapsed_s >= 0

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "gpt-5.4-xhigh" in cmd
        assert "--trust" in cmd
        assert "--force" in cmd
        assert "--mode" not in cmd

    def test_nonzero_exit(self):
        fake_proc = MagicMock()
        fake_proc.returncode = 1
        fake_proc.stdout = ""
        fake_proc.stderr = "error details"

        with (
            patch("shutil.which", return_value="/usr/local/bin/agent"),
            patch("subprocess.run", return_value=fake_proc),
        ):
            result = run_agent("prompt", "gemini-3.1-pro")

        assert result.success is False
        assert result.returncode == 1
        assert "error details" in result.error

    def test_timeout(self):
        import subprocess as sp

        with (
            patch("shutil.which", return_value="/usr/local/bin/agent"),
            patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="agent", timeout=10)),
        ):
            result = run_agent("prompt", "gpt-5.4-xhigh", timeout=10)

        assert result.success is False
        assert "超时" in result.error


class TestModelRegistry:
    def test_three_models_defined(self):
        assert len(SUGGEST_MODELS) == 3

    def test_model_ids_are_strings(self):
        for mid, mname in SUGGEST_MODELS:
            assert isinstance(mid, str)
            assert isinstance(mname, str)
            assert len(mid) > 0
