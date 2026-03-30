"""执行适配器 — Phase 4 扩展占位.

当前仅支持 paper trading（模拟记录）。
真实券商执行需在 Phase 4 实现，且默认保持关闭。
"""

from __future__ import annotations

from enum import Enum


class ExecutionMode(str, Enum):
    PAPER = "paper"
    MANUAL_CONFIRM = "manual_confirm"
    # LIVE = "live"  # Phase 4 — 默认关闭，需人工确认 + 风控通过


class ExecutionAdapter:
    """交易执行适配器基类."""

    def __init__(self, mode: ExecutionMode = ExecutionMode.PAPER):
        self.mode = mode

    def execute(self, **kwargs) -> dict:
        if self.mode == ExecutionMode.PAPER:
            return self._paper_execute(**kwargs)
        elif self.mode == ExecutionMode.MANUAL_CONFIRM:
            return self._manual_confirm(**kwargs)
        else:
            raise NotImplementedError(f"执行模式 {self.mode} 尚未实现")

    def _paper_execute(self, **kwargs) -> dict:
        """模拟执行 — 仅记录，不发送真实订单."""
        return {
            "status": "paper_executed",
            "mode": "paper",
            "details": kwargs,
            "message": "模拟交易已记录。这不是真实交易。",
        }

    def _manual_confirm(self, **kwargs) -> dict:
        """人工确认模式 — 生成待确认的交易指令."""
        return {
            "status": "pending_confirmation",
            "mode": "manual_confirm",
            "details": kwargs,
            "message": "交易指令已生成，请人工确认后执行。",
        }


# --- Phase 4 预留 ---

# class BrokerAdapter(ExecutionAdapter):
#     """券商 API 适配器 — 需要实现:
#     - 账户认证
#     - 订单提交
#     - 订单状态查询
#     - 风控拦截检查
#     - 双重确认机制
#     """
#     pass
