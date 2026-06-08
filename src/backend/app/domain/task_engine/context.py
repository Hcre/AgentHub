"""Coordinator 上下文组装（spec §1.1 gather_context）。

MVP：机械收集仓库元数据 + Agent 注册表 + 约束，全注入 PlanContext。
只读，路径限边界（realpath + startswith workspace），不可越界、不可写。

注意：本模块是**同步** IO 工具（subprocess/文件读）。异步调用方（Orchestrator/
ChatService）须用 `await asyncio.to_thread(gather_context, ...)` 包装，避免阻塞事件循环。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from app.domain.task_engine.ports import PlanContext

logger = logging.getLogger(__name__)

_TREE_DEPTH = 3
_IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist",
    "__pycache__", ".mypy_cache", ".pytest_cache",
}
_STACK_FILES = ["package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml"]
_MAX_TREE_LINES = 200
_MAX_STACK_BYTES = 5 * 1024
_MAX_DOC_BYTES = 30 * 1024


def _safe_workspace_path(workspace: str, relative: str = ".") -> str:
    """路径限边界：防 ../../etc/passwd 越界，锁死在 workspace 内（spec §4/§9）。"""
    root = os.path.realpath(workspace)
    full = os.path.realpath(os.path.join(root, relative))
    if not (full == root or full.startswith(root + os.sep)):
        raise ValueError(f"越界访问被拒: {relative}")
    return full


def _list_tree(workspace: str, max_depth: int = _TREE_DEPTH) -> str:
    root = _safe_workspace_path(workspace)
    if (Path(root) / ".git").exists():
        try:
            result = subprocess.run(
                ["git", "ls-files"], cwd=root,
                capture_output=True, text=True, timeout=10, check=False,
            )
            files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        except (OSError, subprocess.SubprocessError):
            files = []
    else:
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            rel_depth = len(Path(dirpath).relative_to(root).parts)
            if rel_depth >= max_depth:
                dirnames.clear()
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
            for f in filenames:
                files.append(str(Path(dirpath).relative_to(root) / f))

    # 截断到 max_depth，去重，最多 N 行
    trimmed: set[str] = set()
    for f in sorted(files):
        parts = Path(f).parts
        trimmed.add(str(Path(*parts[:max_depth])) + ("/..." if len(parts) > max_depth else ""))
    return "\n".join(sorted(trimmed)[:_MAX_TREE_LINES])


def _read_stack_info(workspace: str) -> str:
    root = _safe_workspace_path(workspace)
    parts = []
    for name in _STACK_FILES:
        path = Path(root) / name
        if path.is_file():
            try:
                content = path.read_text("utf-8", errors="replace")[:_MAX_STACK_BYTES]
                parts.append(f"--- {name} ---\n{content}")
            except OSError:
                continue
    return "\n".join(parts)


def _discover_commands(workspace: str) -> str:
    root = _safe_workspace_path(workspace)
    cmds = []
    pkg_json = Path(root) / "package.json"
    if pkg_json.exists():
        try:
            scripts = json.loads(pkg_json.read_text("utf-8")).get("scripts", {})
            for key in ("test", "build", "lint", "typecheck"):
                if key in scripts:
                    cmds.append(f"npm run {key}")
            if not cmds:
                cmds.append("npx tsc --noEmit")
        except (OSError, json.JSONDecodeError):
            pass
    if (Path(root) / "pyproject.toml").exists() or (Path(root) / "setup.py").exists():
        cmds.append("pytest")
    if (Path(root) / "Makefile").exists():
        cmds.append("make test")
    return ", ".join(cmds)


def _build_agents_desc(workers: list[str]) -> str:
    """构造 Agent 能力描述块。MVP 种子只列名字；标准档补 capability_tags（Phase 5 传完整 Agent）。"""
    return "\n".join(f"- {w}" for w in workers)


def gather_context(
    task_text: str,
    workers: list[str],
    workspace: str | None = None,
    constraints: tuple[str, ...] | None = None,
    design_doc: str | None = None,
    agents_desc: str = "",
) -> PlanContext:
    """组装 PlanContext 种子（spec §1.1/§7.1）。只读，零副作用。

    Args:
        task_text: 用户需求文本
        workers: 群成员 Agent 名（= group.member_ids；空 → plan() 时 PlanEmptyError）
        workspace: 代码仓库路径（None = 纯文本任务，无仓库上下文）
        constraints: 硬约束清单（来自 ContextHandoff）
        design_doc: 用户上传设计文档路径
        agents_desc: 成员富描述（名+角色+能力），调用方有完整 Agent 时传——让 planner
            按能力选 worker，而非只看名字盲选。空 → 退回只列名字。
    """
    repo_tree = ""
    if workspace and os.path.isdir(workspace):
        _safe_workspace_path(workspace)  # 先校验边界
        repo_tree = _list_tree(workspace)
        # stack/commands 当前未进 PlanContext 字段，预留（标准档可注入 prompt）
        _read_stack_info(workspace)
        _discover_commands(workspace)

    doc_text: str | None = None
    if design_doc:
        doc_path = Path(design_doc)
        if doc_path.is_file():
            doc_text = doc_path.read_text("utf-8", errors="replace")[:_MAX_DOC_BYTES]

    return PlanContext(
        task=task_text,
        workers=tuple(workers),
        repo_tree=repo_tree,
        constraints=constraints or (),
        agents_desc=agents_desc or _build_agents_desc(workers),  # 调用方富描述优先，否则名字兜底
        design_doc=doc_text,
    )
