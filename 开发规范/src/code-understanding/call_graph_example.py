"""
调用关系图构建示例 — 基于 AST 遍历

演示如何从 Python 源码中抽取函数/类节点及其调用关系，
构建一个最小可用的代码知识图谱。

对应规范 §2.1 实体抽取 + §2.2 关系抽取（基础层）

用法: python call_graph_example.py [目录路径]
"""

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set


# ── 图谱数据结构 ──────────────────────────────────

@dataclass
class Entity:
    """图谱节点（实体）。对应规范 §1.2 节点类型标准"""
    type: str          # FUNCTION | CLASS | MODULE
    name: str          # 实体名称
    module: str        # 所属模块（文件路径）
    line: int          # 定义所在行号


@dataclass
class Relation:
    """图谱边（关系）。对应规范 §1.3 边类型标准"""
    source: str        # 源实体全限定名
    target: str        # 目标实体全限定名
    rel_type: str      # CALLS | IMPORTS | DEFINES 等


@dataclass
class CodeGraph:
    """代码知识图谱的内存表示"""
    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: List[Relation] = field(default_factory=list)

    def add_entity(self, entity: Entity) -> None:
        key = f"{entity.module}::{entity.name}"
        self.entities[key] = entity

    def add_relation(self, source: str, target: str, rel_type: str) -> None:
        self.relations.append(Relation(source, target, rel_type))

    def find_callers(self, func_name: str) -> List[Relation]:
        """上游分析：谁调用了这个函数？"""
        return [r for r in self.relations
                if func_name in r.target and r.rel_type == "CALLS"]

    def find_callees(self, func_name: str) -> List[Relation]:
        """下游分析：这个函数调用了谁？"""
        return [r for r in self.relations
                if func_name in r.source and r.rel_type == "CALLS"]

    def detect_orphans(self) -> List[str]:
        """检测孤儿节点（无人调用也无人被调用）"""
        called = {r.target for r in self.relations}
        callers = {r.source for r in self.relations}
        all_entities = set(self.entities.keys())
        # 既不是调用者也不是被调用者 = 孤儿节点
        return list(all_entities - called - callers)


# ── AST 遍历器 ────────────────────────────────────

class CallGraphVisitor(ast.NodeVisitor):
    """遍历 AST，抽取函数/类定义 + 调用关系"""

    def __init__(self, module_path: str, graph: CodeGraph):
        self.module_path = module_path
        self.graph = graph
        self.current_function: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # 1. 抽取函数实体
        entity = Entity(
            type="FUNCTION",
            name=node.name,
            module=self.module_path,
            line=node.lineno
        )
        self.graph.add_entity(entity)

        # 记录模块 DEFINED 关系
        self.graph.add_relation(
            self.module_path, f"{self.module_path}::{node.name}", "DEFINES"
        )

        # 2. 遍历函数体内的调用
        prev_func = self.current_function
        self.current_function = f"{self.module_path}::{node.name}"
        self.generic_visit(node)  # 进入函数体
        self.current_function = prev_func

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        entity = Entity(
            type="CLASS",
            name=node.name,
            module=self.module_path,
            line=node.lineno
        )
        self.graph.add_entity(entity)
        self.graph.add_relation(
            self.module_path, f"{self.module_path}::{node.name}", "DEFINES"
        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.current_function is None:
            return

        # 提取被调用函数名
        callee_name = self._resolve_callee(node)
        if callee_name:
            self.graph.add_relation(
                self.current_function,
                f"{self.module_path}::{callee_name}",
                "CALLS"
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.graph.add_relation(
                self.module_path,
                f"__import__::{alias.name}",
                "IMPORTS"
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or "__unknown__"
        for alias in node.names:
            self.graph.add_relation(
                self.module_path,
                f"{module}::{alias.name}",
                "IMPORTS"
            )

    def _resolve_callee(self, node: ast.Call) -> str | None:
        """解析被调用函数名"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None


# ── 主入口 ────────────────────────────────────────

def build_graph(root_dir: str) -> CodeGraph:
    """扫描目录，构建代码知识图谱"""
    graph = CodeGraph()

    py_files = list(Path(root_dir).rglob("*.py"))
    # 跳过 __pycache__ 和测试文件
    py_files = [f for f in py_files
                if "__pycache__" not in str(f)
                and not str(f).endswith("test_")]

    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            module_path = str(py_file.relative_to(root_dir))
            visitor = CallGraphVisitor(module_path, graph)
            visitor.visit(tree)

            # 注册模块实体
            graph.add_entity(Entity("MODULE", module_path, module_path, 1))
        except SyntaxError:
            print(f"  ⚠ 跳过（语法错误）: {py_file}")

    return graph


def print_report(graph: CodeGraph) -> None:
    """输出图谱统计报告"""
    funcs = [e for e in graph.entities.values() if e.type == "FUNCTION"]
    classes = [e for e in graph.entities.values() if e.type == "CLASS"]
    calls = [r for r in graph.relations if r.rel_type == "CALLS"]

    print(f"\n{'='*50}")
    print(f"  代码知识图谱 — 构建报告")
    print(f"{'='*50}")
    print(f"  实体: {len(graph.entities)} 个（函数: {len(funcs)}, 类: {len(classes)}）")
    print(f"  关系: {len(graph.relations)} 条（调用: {len(calls)}）")
    print(f"{'='*50}")

    # 孤儿节点检测
    orphans = graph.detect_orphans()
    if orphans:
        print(f"\n  ⚠ 孤儿节点（无调用者 + 无被调用者）: {len(orphans)} 个")
        for o in orphans[:5]:  # 最多展示 5 个
            print(f"    - {o}")

    # Top 5 被调用最多的函数
    if calls:
        from collections import Counter
        target_counts = Counter(r.target for r in calls)
        print(f"\n  🔥 Top 5 被调用最多的函数:")
        for target, count in target_counts.most_common(5):
            print(f"    - {target} ← 被 {count} 处调用")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"扫描目录: {target}")

    graph = build_graph(target)
    print_report(graph)

    # 示例：查找特定函数的调用者
    print(f"\n  📋 示例 — 查询调用者:")
    for entity_name in list(graph.entities.keys())[:3]:
        callers = graph.find_callers(entity_name.split("::")[-1])
        if callers:
            print(f"    {entity_name} ← 被 {len(callers)} 个调用者")
