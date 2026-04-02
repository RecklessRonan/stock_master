"""Provider路由测试."""
from __future__ import annotations

import pytest

from stock_master.pipeline.providers import DataRouter, get_active_sources_summary


# ---------------------------------------------------------------------------
# DataRouter — 无付费源
# ---------------------------------------------------------------------------

def test_data_router_no_paid():
    router = DataRouter(env={})

    assert not router.has_paid_source()
    assert router.preferred_source("kline") == "akshare"


# ---------------------------------------------------------------------------
# DataRouter — 有付费源
# ---------------------------------------------------------------------------

def test_data_router_with_paid():
    router = DataRouter(env={"SM_IFIND_TOKEN": "test-token-123"})

    assert router.has_paid_source()
    assert router.has_paid_source("ifind")
    assert not router.has_paid_source("wind")
    assert router.preferred_source("kline") == "ifind"


# ---------------------------------------------------------------------------
# fetch_with_fallback — 三级降级
# ---------------------------------------------------------------------------

def test_fetch_with_fallback():
    router = DataRouter(env={"SM_IFIND_TOKEN": "token"})

    # paid 成功
    result, source = router.fetch_with_fallback(
        "valuation",
        free_fn=lambda: {"pe": 10},
        paid_fn=lambda: {"pe": 12, "source": "ifind"},
    )
    assert source == "paid"
    assert result["source"] == "ifind"

    # paid 失败 -> free
    result, source = router.fetch_with_fallback(
        "valuation",
        free_fn=lambda: {"pe": 10},
        paid_fn=lambda: (_ for _ in ()).throw(Exception("paid down")),
    )
    assert source == "free"

    # paid + free 都失败 -> search
    def _fail():
        raise Exception("fail")

    result, source = router.fetch_with_fallback(
        "valuation",
        free_fn=_fail,
        paid_fn=_fail,
        search_fn=lambda: {"pe": 8, "source": "search"},
    )
    assert source == "search"

    # 全部失败
    result, source = router.fetch_with_fallback(
        "valuation",
        free_fn=_fail,
        paid_fn=_fail,
        search_fn=_fail,
    )
    assert result is None
    assert source == "none"


# ---------------------------------------------------------------------------
# get_active_sources_summary
# ---------------------------------------------------------------------------

def test_active_sources_summary():
    summary = get_active_sources_summary(env={})

    assert "akshare" in summary["free"]
    assert summary["has_paid"] is False
    assert isinstance(summary["recommended_upgrades"], list)
    assert len(summary["recommended_upgrades"]) >= 1

    summary_paid = get_active_sources_summary(env={"SM_IFIND_TOKEN": "tok"})
    assert summary_paid["has_paid"] is True
    assert "ifind" in summary_paid["paid"]
