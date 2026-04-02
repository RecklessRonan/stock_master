"""持仓状态管理."""

from __future__ import annotations

from datetime import date

from stock_master.portfolio.trade_log import load_portfolio, save_portfolio


def update_position(
    code: str,
    name: str,
    action: str,
    price: float,
    shares: int,
    strategy: str = "",
    stop_loss: float | None = None,
    take_profit: float | None = None,
    research_ref: str = "",
    notes: str = "",
) -> dict:
    """根据交易更新持仓快照."""
    portfolio = load_portfolio()
    positions = portfolio.get("positions", [])

    existing = None
    for pos in positions:
        if pos["code"] == code:
            existing = pos
            break

    if action in ("buy", "add"):
        if existing:
            total_cost = existing["avg_cost"] * existing["shares"] + price * shares
            total_shares = existing["shares"] + shares
            existing["avg_cost"] = round(total_cost / total_shares, 4) if total_shares > 0 else 0
            existing["shares"] = total_shares
            if strategy:
                existing["strategy"] = strategy
            if stop_loss is not None:
                existing["stop_loss"] = stop_loss
            if take_profit is not None:
                existing["take_profit"] = take_profit
            if research_ref:
                existing["research_ref"] = research_ref
            if notes:
                existing["notes"] = notes
        else:
            positions.append({
                "code": code,
                "name": name,
                "shares": shares,
                "avg_cost": price,
                "strategy": strategy,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "research_ref": research_ref,
                "notes": notes,
            })

    elif action in ("sell", "reduce"):
        if existing:
            # 卖出前记录交易日志
            sell_log = {
                "sold_at": price,
                "sell_date": date.today().isoformat(),
                "sell_reason": notes,
                "sell_shares": shares,
            }
            if existing.get("buy_date"):
                sell_log["buy_date"] = existing["buy_date"]
            if existing.get("buy_reason"):
                sell_log["buy_reason"] = existing["buy_reason"]
            if existing.get("avg_cost"):
                sell_log["avg_cost"] = existing["avg_cost"]
                pnl = round((price - existing["avg_cost"]) * shares, 2)
                pnl_pct = round((price / existing["avg_cost"] - 1) * 100, 2) if existing["avg_cost"] > 0 else 0.0
                sell_log["pnl"] = pnl
                sell_log["pnl_pct"] = pnl_pct

            portfolio.setdefault("sell_log", []).append({
                "code": code,
                "name": name,
                **sell_log,
            })

            existing["shares"] = max(0, existing["shares"] - shares)
            if existing["shares"] == 0:
                positions.remove(existing)

    portfolio["positions"] = positions
    save_portfolio(portfolio)
    return portfolio
