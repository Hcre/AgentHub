"""
CI 集成示例 — 图中缺陷检测 + 覆盖率检查

对应规范 §3.3 缺陷检测模式库 + §6.2 CI 门禁

用法:
    python ci_integration.py --repo <路径>           # 完整检查
    python ci_integration.py --repo <路径> --mode pr  # PR 增量检查

集成到 CI (示例):
    - name: Graph Check
      run: python ci_integration.py --repo . --mode pr
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple


# ── 缺陷检测规则 ──────────────────────────────────

class GraphCheck:
    """单条图检测规则"""

    def __init__(self, name: str, severity: str, description: str):
        self.name = name
        self.severity = severity  # HIGH | MEDIUM | LOW
        self.description = description

    def check(self, graph_data: dict) -> List[dict]:
        """返回违规列表。子类需实现。"""
        raise NotImplementedError


class CyclicDependencyCheck(GraphCheck):
    """循环依赖检测"""

    def __init__(self):
        super().__init__(
            name="cyclic-dependency",
            severity="HIGH",
            description="模块间禁止循环依赖（A → B → A）"
        )

    def check(self, graph_data: dict) -> List[dict]:
        violations = []
        imports = graph_data.get("imports", {})

        # 简化版：检查直接的双向依赖
        for src, targets in imports.items():
            for tgt in targets:
                if tgt in imports and src in imports[tgt]:
                    violations.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "message": f"循环依赖: {src} ⇄ {tgt}",
                        "modules": [src, tgt]
                    })

        return violations


class UnusedFunctionCheck(GraphCheck):
    """未使用函数检测（孤儿节点）"""

    def __init__(self):
        super().__init__(
            name="unused-function",
            severity="MEDIUM",
            description="函数未被任何调用者引用且非入口点"
        )

    def check(self, graph_data: dict) -> List[dict]:
        violations = []
        calls = graph_data.get("calls", {})
        all_callers = set()

        for callers in calls.values():
            all_callers.update(callers)

        functions = graph_data.get("functions", {})
        entrypoints = graph_data.get("entrypoints", set())

        for func_name, func_info in functions.items():
            if func_name not in all_callers and func_name not in entrypoints:
                violations.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "message": f"未使用函数: {func_name} (模块: {func_info.get('module', '?')})",
                    "function": func_name,
                    "module": func_info.get("module", "?")
                })

        return violations


class CrossLayerCheck(GraphCheck):
    """跨层调用检测"""

    LAYER_ORDER = {
        "presentation": 1,
        "application": 2,
        "domain": 3,
        "infrastructure": 4,
    }

    def __init__(self):
        super().__init__(
            name="cross-layer-violation",
            severity="HIGH",
            description="表现层不得直接调用基础设施层"
        )

    def check(self, graph_data: dict) -> List[dict]:
        violations = []
        calls = graph_data.get("calls", {})
        layers = graph_data.get("layers", {})

        for caller, callees in calls.items():
            caller_layer = layers.get(caller)
            if caller_layer is None:
                continue
            for callee in callees:
                callee_layer = layers.get(callee)
                if callee_layer is None:
                    continue
                # 表现层直接调用基础设施层 = 违规
                if (caller_layer == "presentation"
                        and callee_layer == "infrastructure"):
                    violations.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "message": (
                            f"跨层违规: {caller}({caller_layer}) "
                            f"→ {callee}({callee_layer})"
                        ),
                        "caller": caller,
                        "callee": callee
                    })

        return violations


# ── 主检查器 ──────────────────────────────────────

class GraphCI:
    """图谱 CI 检查器"""

    CHECKS = [
        CyclicDependencyCheck(),
        UnusedFunctionCheck(),
        CrossLayerCheck(),
    ]

    def __init__(self, repo_path: str, mode: str = "full"):
        self.repo_path = Path(repo_path)
        self.mode = mode  # full | pr
        self.violations: List[dict] = []
        self.stats = {"total_checks": 0, "passed": 0, "failed": 0}

    def run(self) -> bool:
        """执行所有检查，返回是否全部通过"""
        # 1. 加载图谱数据（实际项目从图DB加载，此处用模拟数据演示）
        graph_data = self._load_graph()

        # 2. 逐个执行检查规则
        for check in self.CHECKS:
            self.stats["total_checks"] += 1
            results = check.check(graph_data)

            if results:
                self.stats["failed"] += 1
                self.violations.extend(results)
                print(f"  ❌ {check.name}: {len(results)} 项违规 — {check.description}")
                for v in results:
                    print(f"     └─ {v['message']}")
            else:
                self.stats["passed"] += 1
                print(f"  ✅ {check.name}: 通过")

        return len(self.violations) == 0

    def _load_graph(self) -> dict:
        """加载图谱数据（实际应从 KuzuDB/Neo4j 加载）"""
        # 模拟数据 — 演示 CI 流程
        return {
            "functions": {
                "place_order": {"module": "services/order.py", "line": 42},
                "calculate_discount": {"module": "domain/discount.py", "line": 15},
                "save_to_db": {"module": "infra/postgres.py", "line": 10},
                "legacy_helper": {"module": "utils/legacy.py", "line": 5},
            },
            "calls": {
                "place_order": ["calculate_discount", "save_to_db"],
                "calculate_discount": [],  # ← 不会被 detect_orphan 标记（有入边）
            },
            "imports": {
                "services/order": ["domain/discount", "infra/postgres"],
                "domain/discount": ["services/order"],  # ← 循环依赖！
            },
            "layers": {
                "place_order": "application",
                "calculate_discount": "domain",
                "save_to_db": "infrastructure",
            },
            "entrypoints": {"place_order"},
        }

    def report(self) -> str:
        """生成 CI 报告"""
        passed = self.stats["passed"]
        total = self.stats["total_checks"]
        return json.dumps({
            "status": "pass" if self.stats["failed"] == 0 else "fail",
            "stats": self.stats,
            "violations_count": len(self.violations),
            "violations": self.violations,
            "summary": f"{passed}/{total} 规则通过"
        }, ensure_ascii=False, indent=2)


# ── CLI ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="代码图谱 CI 检查器")
    parser.add_argument("--repo", default=".", help="仓库路径")
    parser.add_argument("--mode", default="pr",
                        choices=["full", "pr"],
                        help="full=全量, pr=增量")
    parser.add_argument("--output", help="输出 JSON 报告到文件")
    args = parser.parse_args()

    print(f"\n🔍 代码图谱 CI 检查")
    print(f"   仓库: {args.repo}")
    print(f"   模式: {args.mode}")
    print(f"{'─' * 40}")

    ci = GraphCI(args.repo, args.mode)
    passed = ci.run()

    print(f"{'─' * 40}")
    report = ci.report()
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\n📄 报告已写入: {args.output}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
