"""观察清单与机会提醒."""

from __future__ import annotations

from datetime import date


def upsert_watchlist_item(
    watchlist: dict,
    *,
    code: str,
    name: str,
    bucket: str,
    target_price: float | None = None,
    thesis: str = "",
) -> dict:
    """新增或更新观察清单项."""
    stocks = list(watchlist.get("stocks", []))
    existing = next((item for item in stocks if item.get("code") == code), None)
    payload = {
        "code": code,
        "name": name,
        "bucket": bucket,
        "target_price": target_price,
        "thesis": thesis,
        "updated_at": date.today().isoformat(),
    }
    if existing is None:
        stocks.append(payload)
    else:
        existing.update(payload)

    watchlist["updated_at"] = date.today().isoformat()
    watchlist["stocks"] = stocks
    return watchlist


def generate_watchlist_alerts(
    watchlist: dict,
    *,
    dossiers: dict[str, dict] | None = None,
    market_prices: dict[str, float] | None = None,
) -> list[dict]:
    """基于目标价和 dossier 生成机会/风险提醒."""
    dossiers = dossiers or {}
    market_prices = market_prices or {}
    alerts: list[dict] = []

    for item in watchlist.get("stocks", []):
        code = item.get("code", "")
        bucket = item.get("bucket", "ready")
        current_price = market_prices.get(code)
        target_price = item.get("target_price")
        rookie_verdict = dossiers.get(code, {}).get("rookie_action", {}).get("verdict", "")

        if bucket == "wait_price" and current_price is not None and target_price is not None and current_price <= target_price:
            alerts.append(
                {
                    "code": code,
                    "type": "opportunity",
                    "message": f"{code} 已接近目标价，可重新评估。",
                    "bucket": bucket,
                    "current_price": current_price,
                    "target_price": target_price,
                }
            )
        elif rookie_verdict in {"暂时回避", "先补证据"}:
            alerts.append(
                {
                    "code": code,
                    "type": "risk",
                    "message": f"{code} 当前结论为“{rookie_verdict}”，不建议立即行动。",
                    "bucket": bucket,
                }
            )

    return alerts
