"""cursor_agent 模块单元测试."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
import sys

from stock_master.pipeline.cursor_agent import (
    AgentResult,
    SUGGEST_MODELS,
    ensure_agent_available,
    resolve_agent_command,
    resolve_agent_executable,
    run_agent,
)

_MOCK_CMD = patch(
    "stock_master.pipeline.cursor_agent._resolve_win32_node_command",
    return_value=None,
)


class TestEnsureAgentAvailable:
    def test_found(self):
        with _MOCK_CMD, patch("shutil.which", return_value="/usr/local/bin/agent"):
            assert ensure_agent_available() == "/usr/local/bin/agent"

    def test_not_found(self):
        with patch(
            "stock_master.pipeline.cursor_agent.resolve_agent_executable",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="未检测到 agent CLI"):
                ensure_agent_available()


class TestResolveAgentExecutable:
    def test_windows_node_direct(self, tmp_path, monkeypatch):
        """When node.exe + index.js exist in a version dir, prefer them."""
        monkeypatch.setattr(sys, "platform", "win32")
        ver_dir = tmp_path / "cursor-agent" / "versions" / "2026.03.30-a5d3e17"
        ver_dir.mkdir(parents=True)
        (ver_dir / "node.exe").write_bytes(b"")
        (ver_dir / "index.js").write_bytes(b"")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        with patch("shutil.which", return_value=None):
            cmd = resolve_agent_command()
            assert cmd == [str(ver_dir / "node.exe"), str(ver_dir / "index.js")]

    def test_windows_localappdata_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        agent_dir = tmp_path / "cursor-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.cmd").write_bytes(b"@echo off\r\n")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        with _MOCK_CMD, patch("shutil.which", return_value=None):
            assert resolve_agent_executable() == str(agent_dir / "agent.cmd")

    def test_not_found_non_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        with patch("shutil.which", return_value=None):
            assert resolve_agent_executable() is None


class TestRunAgent:
    def test_success(self):
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "建议买入"
        fake_proc.stderr = ""

        with (
            _MOCK_CMD,
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
        assert "--approve-mcps" in cmd
        assert "--mode" not in cmd

    def test_nonzero_exit(self):
        fake_proc = MagicMock()
        fake_proc.returncode = 1
        fake_proc.stdout = ""
        fake_proc.stderr = "error details"

        with (
            _MOCK_CMD,
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
            _MOCK_CMD,
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
