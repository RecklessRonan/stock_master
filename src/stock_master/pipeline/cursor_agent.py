"""Cursor Agent CLI runner — 封装 `agent` 子进程调用."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional


SUGGEST_MODELS: list[tuple[str, str]] = [
    ("gpt-5.4-xhigh", "GPT-5.4 Extra High"),
    ("claude-4.6-opus-high-thinking", "Opus 4.6 Thinking"),
    ("gemini-3.1-pro", "Gemini 3.1 Pro"),
]

SYNTHESIS_MODEL = SUGGEST_MODELS[0]  # gpt-5.4-xhigh


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


def ensure_agent_available() -> str:
    """检查 agent CLI 是否在 PATH 上，返回可执行文件路径.

    Raises:
        RuntimeError: agent 不在 PATH 上。
    """
    path = shutil.which("agent")
    if path is None:
        raise RuntimeError(
            "未检测到 agent CLI。\n"
            "安装方法：curl https://cursor.com/install -fsS | bash"
        )
    return path


def run_agent(
    prompt: str,
    model_id: str,
    display_name: str = "",
    timeout: Optional[int] = None,
) -> AgentResult:
    """调用 agent CLI 并返回结构化结果.

    使用默认 agent 模式（完整工具集），``--trust`` 跳过交互确认，
    ``--print`` 把响应输出到 stdout，``--force`` 允许自动执行命令。
    """
    agent_bin = ensure_agent_available()
    display_name = display_name or model_id

    cmd = [
        agent_bin,
        "--print",
        "--trust",
        "--force",
        "--output-format", "text",
        "--model", model_id,
        prompt,
    ]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            return AgentResult(
                model_id=model_id,
                display_name=display_name,
                output=proc.stdout,
                error=proc.stderr or f"agent exited with code {proc.returncode}",
                returncode=proc.returncode,
                elapsed_s=round(elapsed, 2),
                success=False,
            )

        return AgentResult(
            model_id=model_id,
            display_name=display_name,
            output=proc.stdout,
            error=proc.stderr,
            returncode=0,
            elapsed_s=round(elapsed, 2),
            success=True,
        )

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
