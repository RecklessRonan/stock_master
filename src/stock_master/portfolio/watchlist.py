"""观察清单与机会提醒."""

from __future__ import annotations

from datetime import date

# ---------------------------------------------------------------------------
# 公告/业绩关键词（与 alerts.py 保持一致）
# ---------------------------------------------------------------------------

_POSITIVE_ANNOUNCEMENT_KEYWORDS = ["增持", "回购", "分红", "并购"]
_POSITIVE_EARNINGS_TYPES = {"预增", "扭亏", "略增", "续盈"}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 提醒生成
# ---------------------------------------------------------------------------


def generate_watchlist_alerts(
    watchlist: dict,
    *,
    dossiers: dict[str, dict] | None = None,
    market_prices: dict[str, float] | None = None,
    capital_flows: dict[str, dict] | None = None,
    announcements: dict[str, list] | None = None,
    earnings_forecasts: dict[str, list] | None = None,
) -> list[dict]:
    """基于目标价、dossier、公告、业绩预告和资金流生成机会/风险提醒."""
    dossiers = dossiers or {}
    market_prices = market_prices or {}
    capital_flows = capital_flows or {}
    announcements = announcements or {}
    earnings_forecasts = earnings_forecasts or {}
    alerts: list[dict] = []

    for item in watchlist.get("stocks", []):
        code = item.get("code", "")
        bucket = item.get("bucket", "ready")
        current_price = market_prices.get(code)
        target_price = item.get("target_price")
        rookie_verdict = (
            dossiers.get(code, {}).get("rookie_action", {}).get("verdict", "")
        )

        # --- 原有逻辑：目标价触达 ---
        if (
            bucket == "wait_price"
            and current_price is not None
            and target_price is not None
            and current_price <= target_price
        ):
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
                    "message": f"{code} 当前结论为\u201c{rookie_verdict}\u201d，不建议立即行动。",
                    "bucket": bucket,
                }
            )

        # --- 新增：重要公告提醒 ---
        for ann in announcements.get(code, []):
            title_text = ann.get("title", "")
            matched = [
                kw for kw in _POSITIVE_ANNOUNCEMENT_KEYWORDS if kw in title_text
            ]
            if matched:
                alerts.append(
                    {
                        "code": code,
                        "type": "opportunity",
                        "message": (
                            f"{code} 出现重要公告（{'、'.join(matched)}）：{title_text}"
                        ),
                        "bucket": bucket,
                    }
                )
                break

        # --- 新增：业绩预告利好 ---
        forecasts = earnings_forecasts.get(code, [])
        if forecasts:
            latest = forecasts[0]
            if latest.get("type", "") in _POSITIVE_EARNINGS_TYPES:
                alerts.append(
                    {
                        "code": code,
                        "type": "opportunity",
                        "message": (
                            f"{code} 业绩预告「{latest['type']}」，"
                            f"{latest.get('summary', '关注后续详情')}"
                        ),
                        "bucket": bucket,
                    }
                )

        # --- 新增：主力资金大额净流入 ---
        cf = capital_flows.get(code, {})
        net_inflow = cf.get("main_net_inflow", 0.0)
        if net_inflow >= 5000.0:
            alerts.append(
                {
                    "code": code,
                    "type": "attention",
                    "message": (
                        f"{code} 主力净流入 {net_inflow:.0f} 万元，值得关注。"
                    ),
                    "bucket": bucket,
                }
            )

        # --- 新增：ready 桶 + dossier 建议"可小仓分批"时升级提醒 ---
        if bucket == "ready" and "可小仓分批" in rookie_verdict:
            alerts.append(
                {
                    "code": code,
                    "type": "action",
                    "message": (
                        f"{code} 已 ready，dossier 建议「{rookie_verdict}」，可考虑执行。"
                    ),
                    "bucket": bucket,
                }
            )

    return alerts


# ---------------------------------------------------------------------------
# 分类
# ---------------------------------------------------------------------------


def categorize_watchlist(watchlist: dict) -> dict[str, list[dict]]:
    """按三分类整理观察清单."""
    categories: dict[str, list[dict]] = {
        "ready": [],
        "wait_price": [],
        "avoid": [],
    }
    for stock in watchlist.get("stocks", []):
        bucket = stock.get("bucket", "ready")
        categories.get(bucket, categories["ready"]).append(stock)
    return categories


# ---------------------------------------------------------------------------
# 行动建议
# ---------------------------------------------------------------------------


def suggest_watchlist_actions(
    watchlist: dict,
    dossiers: dict[str, dict],
    market_prices: dict[str, float],
) -> list[dict]:
    """为观察清单中每只股票生成行动建议."""
    suggestions: list[dict] = []

    for stock in watchlist.get("stocks", []):
        code = stock.get("code", "")
        name = stock.get("name", code)
        bucket = stock.get("bucket", "ready")
        target_price = stock.get("target_price")
        current_price = market_prices.get(code)
        dossier = dossiers.get(code, {})
        rookie_verdict = dossier.get("rookie_action", {}).get("verdict", "")

        status = _describe_status(bucket, current_price, target_price)
        action, reason = _decide_action(
            bucket, rookie_verdict, current_price, target_price,
        )

        suggestions.append(
            {
                "code": code,
                "name": name,
                "status": status,
                "action": action,
                "reason": reason,
            }
        )

    return suggestions


def _describe_status(
    bucket: str,
    current_price: float | None,
    target_price: float | None,
) -> str:
    """描述股票当前状态."""
    parts = [f"桶位：{bucket}"]
    if current_price is not None:
        parts.append(f"现价 {current_price:.2f}")
    if target_price is not None:
        parts.append(f"目标 {target_price:.2f}")
    return "，".join(parts)


def _decide_action(
    bucket: str,
    rookie_verdict: str,
    current_price: float | None,
    target_price: float | None,
) -> tuple[str, str]:
    """根据桶位和 dossier 决策行动与理由."""
    if bucket == "avoid":
        return "观望", "当前处于回避状态，暂不操作。"

    if bucket == "wait_price":
        if current_price is not None and target_price is not None:
            if current_price <= target_price:
                return "重新评估", f"已达目标价 {target_price:.2f}，建议更新研究。"
            gap = (current_price - target_price) / target_price * 100
            return "继续等待", f"距目标价还有 {gap:.1f}%，保持耐心。"
        return "继续等待", "等待价格数据更新。"

    # bucket == "ready" 或其他
    if "可小仓分批" in rookie_verdict:
        return "考虑建仓", f"dossier 建议「{rookie_verdict}」。"
    if rookie_verdict in {"暂时回避", "先补证据"}:
        return "补充研究", f"dossier 结论「{rookie_verdict}」，需更多信息。"
    if rookie_verdict:
        return "深入研究", f"dossier 结论「{rookie_verdict}」，评估后再决定。"
    return "撰写 dossier", "尚无研究结论，建议先完成个股研究。"
