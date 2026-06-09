"""gather_context 测试（spec §1.4/§10）。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from app.domain.task_engine.context import (
    _list_tree,
    _safe_workspace_path,
    gather_context,
)


def _git_init_add(path, *files: str) -> None:
    """git init + 写文件 + add（ls-files 只需 staged，无需 commit/user 配置）。"""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    for f in files:
        (path / f).write_text("x")
    subprocess.run(["git", "add", "."], cwd=path, check=True)


class TestSafeWorkspacePath:
    def test_within_workspace(self, tmp_path):
        assert _safe_workspace_path(str(tmp_path), "src").startswith(str(tmp_path.resolve()))

    def test_traversal_blocked(self, tmp_path):
        with pytest.raises(ValueError, match="越界"):
            _safe_workspace_path(str(tmp_path), "../../etc/passwd")

    def test_root_ok(self, tmp_path):
        assert _safe_workspace_path(str(tmp_path)) == os.path.realpath(str(tmp_path))


class TestListTree:
    def test_empty_dir(self, tmp_path):
        assert _list_tree(str(tmp_path)) == ""

    def test_git_repo(self, tmp_path):
        _git_init_add(tmp_path, "a.py", "b.py")
        tree = _list_tree(str(tmp_path))
        assert "a.py" in tree
        assert "b.py" in tree

    def test_non_git_walk(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x")
        # _list_tree 走 os.walk + Path 拼接，Windows 下分隔符是 "\\"。
        # 测试侧改 as_posix 走 POSIX 形式，避免平台耦合。
        tree = _list_tree(str(tmp_path))
        assert "src/main.py" in tree.replace("\\", "/")

    def test_ignore_dirs(self, tmp_path):
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "x.js").write_text("x")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x")
        tree = _list_tree(str(tmp_path))
        assert "src/app.py" in tree.replace("\\", "/")
        assert "node_modules" not in tree


class TestGatherContext:
    def test_basic(self):
        ctx = gather_context("创建登录页", ["前端Agent", "后端Agent"])
        assert ctx.task == "创建登录页"
        assert ctx.workers == ("前端Agent", "后端Agent")
        assert ctx.agents_desc != ""

    def test_empty_workers(self):
        ctx = gather_context("task", [])
        assert ctx.workers == ()
        assert ctx.agents_desc == ""

    def test_with_workspace(self, tmp_path):
        _git_init_add(tmp_path, "main.py")
        ctx = gather_context("task", ["w"], workspace=str(tmp_path))
        assert "main.py" in ctx.repo_tree

    def test_with_constraints(self):
        ctx = gather_context("task", ["w"], constraints=("中文错误提示", "5次锁定"))
        assert "中文错误提示" in ctx.constraints

    def test_with_design_doc(self, tmp_path):
        doc = tmp_path / "design.md"
        doc.write_text("# 设计文档\n内容")
        ctx = gather_context("task", ["w"], design_doc=str(doc))
        assert ctx.design_doc is not None
        assert "设计文档" in ctx.design_doc

    def test_agents_desc_override(self):
        """调用方传富描述（名+角色+能力）→ 用它，planner 不再盲选。"""
        rich = "- 小美（角色：前端；能力：react, ui）"
        ctx = gather_context("task", ["小美"], agents_desc=rich)
        assert "react" in ctx.agents_desc

    def test_agents_desc_fallback_to_names(self):
        """没传富描述 → 退回只列名字。"""
        ctx = gather_context("task", ["w1", "w2"])
        assert "w1" in ctx.agents_desc and "w2" in ctx.agents_desc
