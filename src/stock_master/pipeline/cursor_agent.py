"""Cursor Agent CLI runner — 封装 `agent` 子进程调用."""

from __future__ import annotations

import os
import re
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


SUGGEST_MODELS: list[tuple[str, str]] = [
    ("gpt-5.4-xhigh", "GPT-5.4 Extra High"),
    ("claude-4.6-opus-high-thinking", "Opus 4.6 Thinking"),
    ("gemini-3.1-pro", "Gemini 3.1 Pro"),
]

SYNTHESIS_MODEL = SUGGEST_MODELS[0]  # gpt-5.4-xhigh

_RETRYABLE_ERRORS = ("ENOENT", "cli-config.json", "rate limit", "429", "503")
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 3.0


@dataclass
class AgentResult:
    """单次 agent 调用的结构化结果."""

    model_id: str
    display_name: str
    output: str = ""
    error: str = ""
    returncode: int = 0
    elapsed_s: float = 0.0
    success: bool = True
    extra: dict = field(default_factory=dict)


def _resolve_win32_node_command() -> list[str] | None:
    """On Windows, locate node.exe + index.js inside the cursor-agent
    versions directory and return ``[node_exe, index_js]``.

    Calling node.exe directly bypasses cmd.exe and PowerShell, which both
    mangle special characters (``|``, ``>``, backticks …) in arguments.
    """
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return None
    versions_dir = Path(local) / "cursor-agent" / "versions"
    if not versions_dir.is_dir():
        return None

    version_dirs = [
        d for d in versions_dir.iterdir()
        if d.is_dir() and re.match(r"^\d{4}\.\d{1,2}\.\d{1,2}-[a-f0-9]+$", d.name)
    ]
    if not version_dirs:
        return None

    version_dirs.sort(
        key=lambda d: [int(x) for x in d.name.split("-")[0].split(".")],
        reverse=True,
    )
    latest = version_dirs[0]
    node_exe = latest / "node.exe"
    index_js = latest / "index.js"
    if node_exe.is_file() and index_js.is_file():
        return [str(node_exe), str(index_js)]
    return None


def resolve_agent_command() -> list[str] | None:
    """Return the agent CLI base command as a list of executable components.

    On Windows, prefers ``[node.exe, index.js]`` (bypasses cmd.exe / PS
    escaping) and falls back to the ``.cmd`` wrapper.
    On other platforms, returns ``[agent_binary]``.
    """
    if sys.platform == "win32":
        direct = _resolve_win32_node_command()
        if direct:
            return direct

    found = shutil.which("agent")
    if found:
        return [found]

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            cmd = Path(local) / "cursor-agent" / "agent.cmd"
            if cmd.is_file():
                return [str(cmd)]
        exe = Path.home() / ".local" / "bin" / "agent.exe"
        if exe.is_file():
            return [str(exe)]

    return None


def resolve_agent_executable() -> Optional[str]:
    """解析 agent CLI 路径（PATH 或 Windows 常见安装目录）。"""
    cmd = resolve_agent_command()
    return cmd[0] if cmd else None


def _agent_env() -> dict[str, str]:
    """Extra env vars that the .cmd/.ps1 wrapper would normally set."""
    env = os.environ.copy()
    env.setdefault("CURSOR_INVOKED_AS", "agent.cmd")
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        env.setdefault("NODE_COMPILE_CACHE", str(Path(local) / "cursor-compile-cache"))
    return env


def _agent_missing_message() -> str:
    if sys.platform == "win32":
        return (
            "未检测到 agent CLI。\n"
            "安装（PowerShell）：irm 'https://cursor.com/install?win32=true' | iex\n"
            "安装后请重新打开终端，或确认 PATH 中包含 %LOCALAPPDATA%\\cursor-agent。"
        )
    return (
        "未检测到 agent CLI。\n"
        "安装方法：curl https://cursor.com/install -fsS | bash"
    )


def agent_cli_install_hint() -> str:
    """供 CLI 打印的平台相关安装说明（不含首行「未检测到…」）。"""
    first, _, rest = _agent_missing_message().partition("\n")
    return rest.strip() if rest else first


def ensure_agent_available() -> str:
    """检查 agent CLI 是否可用，返回可执行文件路径.

    Raises:
        RuntimeError: 找不到 agent CLI。
    """
    path = resolve_agent_executable()
    if path is None:
        raise RuntimeError(_agent_missing_message())
    return path


def _is_retryable(stderr: str, elapsed: float) -> bool:
    """判断失败是否为可重试的瞬态错误（文件竞争、速率限制等）."""
    if elapsed > 30:
        return False
    return any(tok in stderr for tok in _RETRYABLE_ERRORS)


def _run_agent_once(
    cmd: list[str],
    timeout: Optional[int],
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def run_agent(
    prompt: str,
    model_id: str,
    display_name: str = "",
    timeout: Optional[int] = None,
) -> AgentResult:
    """调用 agent CLI 并返回结构化结果.

    使用默认 agent 模式（完整工具集 + max mode 由全局配置控制），
    ``--trust`` 跳过工作区信任确认，``--print`` 把响应输出到 stdout，
    ``--force`` 允许自动执行命令，``--approve-mcps`` 跳过 MCP 授权弹窗。

    并发调用时 agent CLI 可能因 cli-config.json 文件锁竞争而瞬时失败，
    本函数内置最多 {_MAX_RETRIES} 次带退避抖动的自动重试。
    """
    cmd_prefix = resolve_agent_command()
    if cmd_prefix is None:
        raise RuntimeError(_agent_missing_message())
    display_name = display_name or model_id

    cmd = [
        *cmd_prefix,
        "--print",
        "--trust",
        "--force",
        "--approve-mcps",
        "--output-format", "text",
        "--model", model_id,
        prompt,
    ]
    env = _agent_env()

    last_result: AgentResult | None = None

    for attempt in range(_MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            proc = _run_agent_once(cmd, timeout, env=env)
            elapsed = time.monotonic() - start

            if proc.returncode == 0:
                return AgentResult(
                    model_id=model_id,
                    display_name=display_name,
                    output=proc.stdout,
                    error=proc.stderr,
                    returncode=0,
                    elapsed_s=round(elapsed, 2),
                    success=True,
                )

            error_msg = proc.stderr or f"agent exited with code {proc.returncode}"
            last_result = AgentResult(
                model_id=model_id,
                display_name=display_name,
                output=proc.stdout,
                error=error_msg,
                returncode=proc.returncode,
                elapsed_s=round(elapsed, 2),
                success=False,
            )

            if attempt < _MAX_RETRIES and _is_retryable(error_msg, elapsed):
                delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 2)
                time.sleep(delay)
                continue

            return last_result

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return AgentResult(
                model_id=model_id,
                display_name=display_name,
                error=f"agent 调用超时（{timeout}s）",
                elapsed_s=round(elapsed, 2),
                success=False,
                returncode=-1,
            )

        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - start
            return AgentResult(
                model_id=model_id,
                display_name=display_name,
                error=str(exc),
                elapsed_s=round(elapsed, 2),
                success=False,
                returncode=-1,
            )

    return last_result  # type: ignore[return-value]
