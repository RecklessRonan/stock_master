"""交易记录 CRUD — YAML 文件存储."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml

from stock_master.models.decision import TradeAction

TRADES_DIR = Path("journal/trades")
PORTFOLIO_PATH = Path("journal/portfolio.yaml")
WATCHLIST_PATH = Path("journal/watchlist.yaml")


def record_trade(
    code: str,
    action: str,
    price: float,
    shares: int,
    name: str = "",
    reason: str = "",
    research_ref: str = "",
    confidence: int = 5,
    tags: list[str] | None = None,
    review_date: str = "",
) -> Path:
    """记录一笔交易到 YAML 文件."""
    TRADES_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    filename = f"{today}-{code}-{action}.yaml"
    filepath = TRADES_DIR / filename

    counter = 1
    while filepath.exists():
        filename = f"{today}-{code}-{action}-{counter}.yaml"
        filepath = TRADES_DIR / filename
        counter += 1

    trade_data = {
        "date": today,
        "code": code,
        "name": name,
        "action": action,
        "price": price,
        "shares": shares,
        "amount": round(price * shares, 2),
        "reason": reason,
        "research_ref": research_ref,
        "confidence": confidence,
        "tags": tags or [],
        "review_date": review_date,
        "created_at": datetime.now().isoformat(),
    }

    filepath.write_text(
        yaml.dump(trade_data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return filepath


def list_trades(code: Optional[str] = None) -> list[dict]:
    """列出交易记录."""
    if not TRADES_DIR.exists():
        return []

    trades = []
    for f in sorted(TRADES_DIR.glob("*.yaml")):
        with open(f, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            if data and (code is None or data.get("code") == code):
                data["_file"] = str(f)
                trades.append(data)
    return trades


def load_portfolio() -> dict:
    """加载当前持仓快照."""
    if not PORTFOLIO_PATH.exists():
        return {"updated_at": date.today().isoformat(), "positions": []}
    with open(PORTFOLIO_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"updated_at": date.today().isoformat(), "positions": []}


def save_portfolio(data: dict) -> None:
    """保存持仓快照."""
    PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = date.today().isoformat()
    PORTFOLIO_PATH.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def load_watchlist() -> dict:
    """加载自选股列表."""
    if not WATCHLIST_PATH.exists():
        return {"updated_at": date.today().isoformat(), "stocks": []}
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"updated_at": date.today().isoformat(), "stocks": []}


def save_watchlist(data: dict) -> None:
    """保存自选股列表."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = date.today().isoformat()
    WATCHLIST_PATH.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
