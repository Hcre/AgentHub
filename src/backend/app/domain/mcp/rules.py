"""MCP 领域业务规则（集中实现，MD-MCP §6）。

纯函数 + 校验，不依赖 ORM/框架（AR-01）。args_hash 用于安装幂等去重（F-024）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.exceptions import DomainError, ValidationError

MAX_BATCH_INSTALL = 50  # F-022：单 workspace 批量安装上限
MAX_VERSION_LEN = 50  # F-020：version 字符串上限


def compute_args_hash(config: dict[str, Any] | None) -> str:
    """args_hash = SHA256(sorted_json(config))（F-024 幂等去重）。

    sort_keys 保证字段顺序无关，separators 去空白保证跨进程稳定；
    返回 64 位十六进制（对齐列 String(64)）。
    """
    canonical = json.dumps(config or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_version(version: str) -> None:
    """version 非空且 ≤ 50 字符（F-020）。"""
    if not version or not version.strip():
        raise DomainError("MCP version 不能为空")
    if len(version) > MAX_VERSION_LEN:
        raise ValidationError(f"MCP version 字符串超过 {MAX_VERSION_LEN} 字符")


def validate_batch_size(count: int) -> None:
    """单 workspace 批量安装 ≤ 50（F-022）。"""
    if count > MAX_BATCH_INSTALL:
        raise ValidationError(f"单 workspace 批量安装超过 {MAX_BATCH_INSTALL} 上限")
