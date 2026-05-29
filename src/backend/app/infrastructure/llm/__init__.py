"""LLM 适配器实现（实现 L2 的 UnifiedAgent 抽象）。"""

from app.infrastructure.llm.factory import build_adapter
from app.infrastructure.llm.mock_adapter import MockAdapter

__all__ = ["MockAdapter", "build_adapter"]
