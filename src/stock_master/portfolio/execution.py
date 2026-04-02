"""执行适配器 — Phase 4 扩展占位.

当前仅支持 paper trading（模拟记录）。
真实券商执行需在 Phase 4 实现，且默认保持关闭。
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path

import yaml


class ExecutionMode(str, Enum):
    PAPER = "paper"
    MANUAL_CONFIRM = "manual_confirm"
    # LIVE = "live"  # Phase 4 — 默认关闭，需人工确认 + 风控通过


# ---------------------------------------------------------------------------
# 4a. PaperPortfolio — 模拟盘组合管理
# ---------------------------------------------------------------------------

class PaperPortfolio:
    """模拟盘组合管理."""

    PAPER_PATH = Path("journal/paper_portfolio.yaml")

    def __init__(self) -> None:
        self.data = self._load()

    def _load(self) -> dict:
        if not self.PAPER_PATH.exists():
            return {
                "created_at": date.today().isoformat(),
                "updated_at": date.today().isoformat(),
                "initial_cash": 1_000_000.0,
                "cash": 1_000_000.0,
                "positions": [],
                "trade_history": [],
            }
        with open(self.PAPER_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return {
                "created_at": date.today().isoformat(),
                "updated_at": date.today().isoformat(),
                "initial_cash": 1_000_000.0,
                "cash": 1_000_000.0,
                "positions": [],
                "trade_history": [],
            }
        return data

    def _save(self) -> None:
        self.data["updated_at"] = datetime.now().isoformat()
        self.PAPER_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.PAPER_PATH.write_text(
            yaml.dump(self.data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def execute_trade(
        self,
        code: str,
        name: str,
        action: str,
        price: float,
        shares: int,
        reason: str = "",
    ) -> dict:
        """在模拟盘中执行一笔交易."""
        amount = round(price * shares, 2)
        positions: list[dict] = self.data.get("positions", [])

        existing = None
        for pos in positions:
            if pos.get("code") == code:
                existing = pos
                break

        if action in ("buy", "add"):
            if self.data["cash"] < amount:
                return {"status": "rejected", "message": f"现金不足：需要 {amount}，可用 {self.data['cash']:.2f}"}
            self.data["cash"] = round(self.data["cash"] - amount, 2)
            if existing:
                total_cost = existing["avg_cost"] * existing["shares"] + amount
                total_shares = existing["shares"] + shares
                existing["avg_cost"] = round(total_cost / total_shares, 4) if total_shares > 0 else 0
                existing["shares"] = total_shares
                existing["current_price"] = price
            else:
                positions.append({
                    "code": code,
                    "name": name,
                    "shares": shares,
                    "avg_cost": price,
                    "current_price": price,
                    "buy_date": date.today().isoformat(),
                })

        elif action in ("sell", "reduce"):
            if not existing or existing["shares"] < shares:
                avail = existing["shares"] if existing else 0
                return {"status": "rejected", "message": f"持仓不足：需要 {shares} 股，可用 {avail}"}
            self.data["cash"] = round(self.data["cash"] + amount, 2)
            existing["shares"] -= shares
            existing["current_price"] = price
            if existing["shares"] == 0:
                positions.remove(existing)
        else:
            return {"status": "rejected", "message": f"未知操作类型：{action}"}

        self.data["positions"] = positions

        trade_record = {
            "date": date.today().isoformat(),
            "time": datetime.now().strftime("%H:%M:%S"),
            "code": code,
            "name": name,
            "action": action,
            "price": price,
            "shares": shares,
            "amount": amount,
            "reason": reason,
            "cash_after": self.data["cash"],
        }
        self.data.setdefault("trade_history", []).append(trade_record)
        self._save()

        return {
            "status": "paper_executed",
            "trade": trade_record,
            "message": f"模拟交易已执行：{action} {name}({code}) {shares}股 @ {price}",
        }

    def get_positions(self) -> list[dict]:
        """获取当前持仓列表."""
        return self.data.get("positions", [])

    def get_performance(self) -> dict:
        """计算模拟盘收益率."""
        initial = float(self.data.get("initial_cash", 1_000_000))
        cash = float(self.data.get("cash", 0))
        positions = self.data.get("positions", [])

        position_value = 0.0
        position_details: list[dict] = []
        for pos in positions:
            current = float(pos.get("current_price", pos.get("avg_cost", 0)) or 0)
            shares = int(pos.get("shares", 0))
            mv = current * shares
            position_value += mv
            avg_cost = float(pos.get("avg_cost", 0) or 0)
            pnl = (current - avg_cost) * shares if avg_cost > 0 else 0.0
            position_details.append({
                "code": pos.get("code", ""),
                "name": pos.get("name", ""),
                "shares": shares,
                "avg_cost": avg_cost,
                "current_price": current,
                "market_value": round(mv, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl / (avg_cost * shares) * 100, 2) if avg_cost * shares > 0 else 0.0,
            })

        total_assets = cash + position_value
        total_pnl = total_assets - initial
        total_return_pct = round(total_pnl / initial * 100, 2) if initial > 0 else 0.0

        return {
            "initial_cash": initial,
            "cash": round(cash, 2),
            "position_value": round(position_value, 2),
            "total_assets": round(total_assets, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": total_return_pct,
            "position_details": position_details,
            "trade_count": len(self.data.get("trade_history", [])),
        }


# ---------------------------------------------------------------------------
# 4b. ExecutionAdapter 连接 PaperPortfolio
# ---------------------------------------------------------------------------

class ExecutionAdapter:
    """交易执行适配器基类."""

    def __init__(self, mode: ExecutionMode = ExecutionMode.PAPER):
        self.mode = mode
        self._paper_portfolio: PaperPortfolio | None = None

    def _get_paper_portfolio(self) -> PaperPortfolio:
        if self._paper_portfolio is None:
            self._paper_portfolio = PaperPortfolio()
        return self._paper_portfolio

    def execute(self, **kwargs) -> dict:
        if self.mode == ExecutionMode.PAPER:
            return self._paper_execute(**kwargs)
        elif self.mode == ExecutionMode.MANUAL_CONFIRM:
            return self._manual_confirm(**kwargs)
        else:
            raise NotImplementedError(f"执行模式 {self.mode} 尚未实现")

    def _paper_execute(self, **kwargs) -> dict:
        """模拟执行 — 调用 PaperPortfolio 记录交易."""
        pp = self._get_paper_portfolio()
        code = kwargs.get("code", "")
        name = kwargs.get("name", "")
        action = kwargs.get("action", "buy")
        price = float(kwargs.get("price", 0) or 0)
        shares = int(kwargs.get("shares", 0) or 0)
        reason = kwargs.get("reason", "")

        if code and price > 0 and shares > 0:
            return pp.execute_trade(code, name, action, price, shares, reason)

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
