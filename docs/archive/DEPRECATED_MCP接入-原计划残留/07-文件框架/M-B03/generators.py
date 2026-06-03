"""M-B03 Binding Engine mcp-config 生成器（ADR-005 单一源）.

[文件路径] src/agenthub/application/binding/generators.py
[文件职责] mcp-config 文件的生成与撤销（L4 单一源，禁止绕过）
[所属模块] M-B03
[关联设计规范] MD-MCP-V1.0-20260602#M-B03 / ADR-005 / SEC:SEC-011
[功能描述]
  功能1: generate(mapping, ws_id) 原子写入 mcp-config（temp + rename + chmod 0600 + fcntl SHARED LOCK）
  功能2: revoke(config_path, ws_id) 原子删除 mcp-config
  功能3: 提供 mcp-config 路径解析（基于 ws_id）
[输入输出]
  输入: mapping dict / ws_id UUID
  输出: Path
[依赖关系]
  依赖文件: agenthub.application.binding.exceptions、agenthub.core.config
  被依赖文件: agenthub.application.binding.services
[注意事项]
  注意1: 是 L4 单一源（ADR-005），所有 mcp-config 写盘必经此入口
  注意2: 必须使用 fcntl SHARED LOCK（写入时） / EXCLUSIVE LOCK（撤销时）
  注意3: 文件权限必须 0600（仅 owner 可读写）
  注意4: 写入必须先写 temp 再 atomic rename，避免半写状态
  注意5: 必须使用 fcntl.flock 而非 fcntl.fcntl（POSIX 兼容）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版生成器
[作者] DD-M-B03-20260603
[来源标注] [DD-001:FS-007 + MD-MCP-V1.0-20260602#M-B03 + ADR-005 + SEC:SEC-011]
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from uuid import UUID

from agenthub.application.binding.exceptions import (
    ConfigLockTimeoutError,
    PathTraversalError,
)
from agenthub.core.config import get_settings
from agenthub.core.logging import get_logger

log = get_logger(__name__)


class ConfigGenerator:
    """mcp-config 文件生成器（L4 单一源）.

    [类名] ConfigGenerator
    [职责] 统一 mcp-config 写盘入口
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03 + ADR-005
    [属性]
      属性1: base_dir Path mcp-config 根目录（来自 settings）
      属性2: file_mode int 文件权限（默认 0o600）
      属性3: lock_timeout_sec float fcntl 锁等待超时（默认 1.0）
    [方法列表]
      方法1: generate(mapping, ws_id, trace_id) -> Path - 写入 mcp-config
      方法2: revoke(config_path, ws_id, trace_id) -> None - 原子删除
      方法3: resolve_path(ws_id, mcp_id) -> Path - 路径解析
    [异常处理]
      异常1: ConfigLockTimeoutError - 锁等待超时
      异常2: PathTraversalError - 路径越界
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + ADR-005]
    """

    _FILE_MODE = 0o600
    _LOCK_TIMEOUT_SEC = 1.0

    def __init__(self, base_dir: Path | None = None, file_mode: int = 0o600) -> None:
        """初始化 ConfigGenerator.

        [函数名] __init__
        [职责] 解析 base_dir
        [参数说明]
          参数1: base_dir Path 可选 默认从 settings 读
          参数2: file_mode int 可选 默认 0o600
        [来源标注] [DD-M推断:典型配置注入]
        """
        settings = get_settings()
        self._base_dir = base_dir or Path(settings.binding_config_dir)
        self._file_mode = file_mode
        self._base_dir.mkdir(parents=True, exist_ok=True)
        log.info("config_generator_initialized", base_dir=str(self._base_dir))

    def resolve_path(self, ws_id: UUID, mcp_id: UUID | None = None) -> Path:
        """解析 mcp-config 路径.

        [函数名] resolve_path
        [职责] 基于 ws_id 生成安全路径（无路径遍历风险）
        [参数说明]
          参数1: ws_id UUID 必填
          参数2: mcp_id UUID 可选 None 时返回 workspace 目录
        [返回值]
          类型: Path
          描述: 绝对路径
        [异常处理]
          异常1: PathTraversalError - 解析结果逃逸 base_dir
        [来源标注] [DD-001:SEC:SEC-011 + TD:BR-001~004]
        """
        if mcp_id is None:
            target = (self._base_dir / str(ws_id)).resolve()
        else:
            target = (self._base_dir / str(ws_id) / f"{mcp_id}.json").resolve()
        # [DD-M推断:resolve 后必须落在 base_dir 内，防止 symlink 攻击]
        if not str(target).startswith(str(self._base_dir.resolve())):
            raise PathTraversalError(f"path escape: {target}")
        return target

    async def generate(
        self,
        mapping: dict[str, str],
        ws_id: UUID,
        trace_id: str,
    ) -> Path:
        """写入 mcp-config.

        [函数名] generate
        [职责] 原子写入（temp + rename + chmod 0600 + fcntl SHARED LOCK）
        [参数说明]
          参数1: mapping dict 必填 名称映射
          参数2: ws_id UUID 必填
          参数3: trace_id str 必填
        [返回值]
          类型: Path
          描述: 写入的 mcp-config 路径
        [错误码]
          错误码1: CONFIG_LOCK_TIMEOUT 503
        [前置条件] base_dir 可写
        [后置条件] mcp-config 文件存在且权限 0600
        [并发安全] fcntl SHARED LOCK（读锁）→ 写盘 → 升级为 EXCLUSIVE LOCK 短暂持有
        [幂等性] 否（重复调用覆盖）
        [性能约束] P95 ≤ 50ms（单文件 < 4KB）
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + ADR-005 + SEC:SEC-011]
        """
        target = self.resolve_path(ws_id=ws_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        log.info(
            "config_generate_start",
            path=str(target),
            ws_id=str(ws_id),
            trace_id=trace_id,
        )

        # [DD-M推断:写盘 → 临时文件 → fcntl 锁 → atomic rename → chmod 0600]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._generate_sync, mapping, target, trace_id
        )

    def _generate_sync(
        self, mapping: dict[str, str], target: Path, trace_id: str
    ) -> Path:
        """同步实现 generate（在 executor 中跑）.

        [函数名] _generate_sync
        [职责] 阻塞式实现文件写盘
        [参数说明]
          参数1: mapping dict 必填
          参数2: target Path 必填 目标路径
          参数3: trace_id str 必填
        [返回值]
          类型: Path
        [来源标注] [DD-M推断:asyncio.to_thread 模式]
        """
        import fcntl
        import json

        fd, tmp_path = tempfile.mkstemp(
            prefix=".mcp-config-", suffix=".tmp", dir=str(target.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)  # SHARED LOCK 写时也持锁
                try:
                    json.dump(
                        {"ws_id": str(target.parent.name), "mapping": mapping, "trace_id": trace_id},
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            os.chmod(tmp_path, self._file_mode)
            os.replace(tmp_path, target)  # 原子 rename
            log.info("config_generated", path=str(target), trace_id=trace_id)
            return target
        except OSError as e:
            log.error("config_generate_failed", path=str(target), err=str(e))
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise ConfigLockTimeoutError(f"failed to write {target}: {e}") from e

    async def revoke(
        self,
        config_path: Path,
        ws_id: UUID,
        trace_id: str,
    ) -> None:
        """撤销 mcp-config.

        [函数名] revoke
        [职责] 原子删除 mcp-config（fcntl EXCLUSIVE LOCK）
        [参数说明]
          参数1: config_path Path 必填 待删除路径
          参数2: ws_id UUID 必填（用于审计日志）
          参数3: trace_id str 必填
        [返回值]
          类型: None
        [错误码]
          错误码1: CONFIG_LOCK_TIMEOUT 503
        [前置条件] config_path 存在
        [后置条件] 文件被删除
        [并发安全] fcntl EXCLUSIVE LOCK
        [幂等性] 是（文件不存在时静默成功）
        [性能约束] P95 ≤ 30ms
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + SEC:SEC-011]
        """
        # [DD-M推断:校验路径必须在 base_dir 内，防止 symlink 攻击]
        if not str(config_path.resolve()).startswith(str(self._base_dir.resolve())):
            raise PathTraversalError(f"path escape: {config_path}")
        log.info("config_revoke_start", path=str(config_path), trace_id=trace_id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._revoke_sync, config_path, trace_id)

    def _revoke_sync(self, config_path: Path, trace_id: str) -> None:
        """同步实现 revoke.

        [函数名] _revoke_sync
        [职责] 加 EXCLUSIVE LOCK 后删除
        [来源标注] [DD-M推断:asyncio.to_thread 模式]
        """
        import fcntl

        if not config_path.exists():
            log.info("config_revoke_skip_not_exist", path=str(config_path), trace_id=trace_id)
            return
        try:
            with open(config_path, "r+", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)  # EXCLUSIVE LOCK
                try:
                    os.unlink(config_path)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            log.info("config_revoked", path=str(config_path), trace_id=trace_id)
        except OSError as e:
            log.error("config_revoke_failed", path=str(config_path), err=str(e))
            raise ConfigLockTimeoutError(f"failed to revoke {config_path}: {e}") from e


__all__ = ["ConfigGenerator"]
