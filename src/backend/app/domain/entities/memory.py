"""Memory 域实体（V3 记忆系统，见 memory-system-design-v3.md）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Memory:
    id: UUID
    agent_id: UUID
    user_id: UUID
    scope: str           # 'agent' | 'group'
    name: str            # 简短标识（≤150 字符）
    description: str     # LLM 检索关键字段（≤300 字符）
    memory_type: str     # facts | preferences | procedures | context
    content: str
    source: str          # manual | chat | system
    pinned: bool
    hits: int
    metadata: dict
    group_id: UUID | None
    created_at: datetime
    updated_at: datetime
