"""模型 Provider 抽象层 — Phase 4 扩展占位.

当前仅定义接口协议。后续可实现 CursorCliProvider、OpenAIProvider、
AnthropicProvider、GeminiProvider 等具体适配器。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ModelProvider(ABC):
    """模型调用的统一抽象接口."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """调用模型生成文本."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Provider 名称."""
        ...


class ManualProvider(ModelProvider):
    """占位 Provider — 表示由人类在 Cursor 中手动完成.

    这是当前默认使用的 provider，所有调研通过 Cursor IDE 交互完成，
    而非 API 自动调用。
    """

    def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        raise NotImplementedError(
            "ManualProvider 不支持自动调用。"
            "请在 Cursor 中手动完成此调研步骤。"
        )

    def name(self) -> str:
        return "manual"


# --- 以下为 Phase 4 预留接口 ---

# class CursorCliProvider(ModelProvider):
#     """通过 Cursor CLI 调用模型."""
#     ...

# class OpenAIProvider(ModelProvider):
#     """通过 OpenAI API 调用."""
#     ...

# class AnthropicProvider(ModelProvider):
#     """通过 Anthropic API 调用."""
#     ...

# class GeminiProvider(ModelProvider):
#     """通过 Google Gemini API 调用."""
#     ...


class DataProviderKind(str, Enum):
    """数据源分类."""

    FREE = "free"
    PAID = "paid"
    SEARCH = "search"


@dataclass(frozen=True)
class DataProviderSpec:
    """数据源配置描述."""

    name: str
    kind: DataProviderKind
    description: str
    env_var: str = ""
    enabled: bool = True


def get_data_provider_catalog(env: Optional[dict[str, str]] = None) -> list[DataProviderSpec]:
    """返回当前可识别的数据源目录."""
    env = env or os.environ
    return [
        DataProviderSpec(
            name="akshare",
            kind=DataProviderKind.FREE,
            description="默认免费行情与基础财务数据源",
            enabled=True,
        ),
        DataProviderSpec(
            name="web_search",
            kind=DataProviderKind.SEARCH,
            description="联网搜索补充最新事件与外部观点",
            enabled=True,
        ),
        DataProviderSpec(
            name="ifind",
            kind=DataProviderKind.PAID,
            description="同花顺 iFinD 付费数据",
            env_var="SM_IFIND_TOKEN",
            enabled=bool(env.get("SM_IFIND_TOKEN")),
        ),
        DataProviderSpec(
            name="choice",
            kind=DataProviderKind.PAID,
            description="东方财富 Choice 付费数据",
            env_var="SM_CHOICE_TOKEN",
            enabled=bool(env.get("SM_CHOICE_TOKEN")),
        ),
        DataProviderSpec(
            name="wind",
            kind=DataProviderKind.PAID,
            description="Wind 付费数据",
            env_var="SM_WIND_TOKEN",
            enabled=bool(env.get("SM_WIND_TOKEN")),
        ),
    ]


def summarize_data_provider_catalog(env: Optional[dict[str, str]] = None) -> dict[str, list[str]]:
    """按来源分类汇总数据源."""
    summary = {"free": [], "paid": [], "search": []}
    for provider in get_data_provider_catalog(env):
        if provider.enabled:
            summary[provider.kind.value].append(provider.name)
    return summary


# ---------------------------------------------------------------------------
# DataRouter — 数据获取路由
# ---------------------------------------------------------------------------


class DataRouter:
    """数据获取路由器 — 根据可用数据源选择最佳路径."""

    def __init__(self, env: Optional[dict[str, str]] = None):
        self.catalog = get_data_provider_catalog(env)
        self._enabled_paid = [
            p for p in self.catalog if p.kind == DataProviderKind.PAID and p.enabled
        ]

    def has_paid_source(self, name: str = "") -> bool:
        if name:
            return any(p.name == name and p.enabled for p in self._enabled_paid)
        return bool(self._enabled_paid)

    def preferred_source(self, data_type: str) -> str:
        """根据数据类型返回首选数据源名称."""
        if self._enabled_paid:
            return self._enabled_paid[0].name
        return "akshare"

    def fetch_with_fallback(
        self,
        data_type: str,
        free_fn,
        paid_fn=None,
        search_fn=None,
        **kwargs,
    ):
        """按优先级尝试获取数据：paid -> free -> search."""
        if paid_fn and self.has_paid_source():
            try:
                result = paid_fn(**kwargs)
                if result:
                    return result, "paid"
            except Exception:
                pass
        try:
            result = free_fn(**kwargs)
            if result:
                return result, "free"
        except Exception:
            pass
        if search_fn:
            try:
                result = search_fn(**kwargs)
                if result:
                    return result, "search"
            except Exception:
                pass
        return None, "none"


# ---------------------------------------------------------------------------
# 数据源摘要与升级建议
# ---------------------------------------------------------------------------


def _recommend_upgrades(router: DataRouter) -> list[str]:
    """基于当前配置推荐数据源升级."""
    recs: list[str] = []
    if not router.has_paid_source():
        recs.append("建议接入 iFinD 或 Choice 获取更完整的财务和资金流数据")
    return recs


def get_active_sources_summary(env: Optional[dict[str, str]] = None) -> dict:
    """返回当前活跃数据源的详细摘要."""
    router = DataRouter(env)
    return {
        "free": [
            p.name for p in router.catalog if p.kind == DataProviderKind.FREE and p.enabled
        ],
        "paid": [
            p.name for p in router.catalog if p.kind == DataProviderKind.PAID and p.enabled
        ],
        "search": [
            p.name for p in router.catalog if p.kind == DataProviderKind.SEARCH and p.enabled
        ],
        "has_paid": router.has_paid_source(),
        "recommended_upgrades": _recommend_upgrades(router),
    }
