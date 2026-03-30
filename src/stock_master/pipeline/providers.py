"""模型 Provider 抽象层 — Phase 4 扩展占位.

当前仅定义接口协议。后续可实现 CursorCliProvider、OpenAIProvider、
AnthropicProvider、GeminiProvider 等具体适配器。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
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
