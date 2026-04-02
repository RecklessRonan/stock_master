"""数据源 Provider 注册表测试."""

from __future__ import annotations

from stock_master.pipeline.providers import get_data_provider_catalog, summarize_data_provider_catalog


def test_paid_data_providers_follow_env_flags():
    catalog = get_data_provider_catalog({"SM_IFIND_TOKEN": "token-1"})
    by_name = {provider.name: provider for provider in catalog}

    assert by_name["akshare"].enabled is True
    assert by_name["web_search"].enabled is True
    assert by_name["ifind"].enabled is True
    assert by_name["choice"].enabled is False
    assert by_name["wind"].enabled is False


def test_summarize_data_provider_catalog_groups_by_kind():
    summary = summarize_data_provider_catalog({"SM_CHOICE_TOKEN": "token-2"})

    assert "free" in summary
    assert "paid" in summary
    assert "search" in summary
    assert "akshare" in summary["free"]
    assert "choice" in summary["paid"]
