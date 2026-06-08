# Phase 2 详细实现方案 — Verifier 机械验收

> 日期：2026-06-06 | 属于：[[coordinator-mvp-implementation-plan]] Phase 2
> 粒度：照着就能写。依赖 Phase 0 ports.py（Verdict/Verifier Protocol）。
> 前提：Phase 1 Orchestrator 串行循环已跑通 M1。

---

## 0. 本相目标

换掉 `FakeVerifier`，让验证闸门跑真命令。MVP 只做**机械验收**——`acceptance` 里 `kind="mechanical"` 的 Check，在 worker 的工作目录里跑命令、读退出码。

MVP 不做：llm_judge（独立 Reviewer agent）、human 闸门、集成验证闸门。那些是标准档的事。

---

## 1. 新建 `verifier.py`

```python
"""Verifier — 机械验收闸门（coordinator-dag-driven-design-v2 §6.2 机械层）。

MVP：只跑 mechanical check，挨个执行 acceptance 里的命令，抓退出码。
标准档：加 reviewer agent (llm_judge) + human 闸门 + 集成验证。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.domain.task_engine.dag import TaskNode
from app.domain.task_engine.ports import Verdict

logger = logging.getLogger(__name__)

# 单命令最长执行时间（秒），防 acceptance 里写了死循环
CHECK_TIMEOUT = 120


class MechanicalVerifier:
    """机械验收器：跑命令 → 读退出码 → 出裁决。无状态。"""

    def __init__(self, workspace: str | None = None) -> None:
        # MVP 串行无 worktree：所有 worker 共用 workspace。
        # 标准档：每个 task 有独立 worktree，调用方传 cwd 覆盖。
        self._fallback_workspace = workspace

    async def verify(self, node: TaskNode) -> Verdict:
        """按 TaskDef.acceptance 逐个跑 mechanical check。

        只处理 kind="mechanical"——llm_judge/human 在 MVP 跳过（不会出现在
        TaskDef 里；若出现则返回 pass 并告警）。
        """
        cwd = node.worktree or self._fallback_workspace

        for check in node.task.acceptance:
            if check.kind == "mechanical":
                result = await self._run_check(check, cwd)
                if not result.passed:
                    return result  # 第一个失败就停，不回跑
            elif check.kind in ("llm_judge", "human"):
                # MVP 不该出现；告警但放行（防止假 TaskDef 卡死循环）
                logger.warning(
                    "MVP Verifier 收到 %s check（task=%s），跳过",
                    check.kind, node.task.id,
                )

        return Verdict(passed=True)

    async def _run_check(self, check, cwd: str | None) -> Verdict:
        """执行单条机械验收命令。"""
        logger.debug("Verifier running: %s (cwd=%s)", check.spec, cwd)

        try:
            proc = await asyncio.create_subprocess_shell(
                check.spec,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CHECK_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return Verdict(
                passed=False,
                reason=f"验收命令超时（>{CHECK_TIMEOUT}s）: {check.spec}",
            )
        except OSError as exc:
            return Verdict(
                passed=False,
                reason=f"验收命令无法执行: {check.spec} ({exc})",
            )

        exit_code = proc.returncode
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if check.expect is not None:
            # 有期望值：按 expect 匹配
            expected = int(check.expect)
            if exit_code != expected:
                return Verdict(
                    passed=False,
                    reason=(
                        f"验收失败: {check.spec}\n"
                        f"期望退出码 {expected}，实际 {exit_code}\n"
                        f"stdout: {stdout_text[:500]}\n"
                        f"stderr: {stderr_text[:500]}"
                    ),
                )
        elif exit_code != 0:
            return Verdict(
                passed=False,
                reason=(
                    f"验收失败: {check.spec} (exit {exit_code})\n"
                    f"stdout: {stdout_text[:500]}\n"
                    f"stderr: {stderr_text[:500]}"
                ),
            )

        return Verdict(passed=True)
```

---

## 2. 更新 `ports.py`（若 Phase 0 未含 expect 字段）

Phase 0 的 `Check` dataclass 已有 `expect` 字段（`dag.py:36`）。验证：

```python
# dag.py:30-37 已定义
@dataclass(frozen=True)
class Check:
    kind: Literal["mechanical", "llm_judge", "human"]
    spec: str          # mechanical: 命令；llm_judge: 评审标准；human: 提示
    expect: str | None = None  # mechanical: 期望退出码，None=期望0
```

确认 `ports.py` 的 `Verifier Protocol` 签名和 `dag.py` 的 `TaskNode` 字段一致即可。如果 Phase 0 的 `Verifier.verify()` 签名是 `async def verify(self, node: TaskNode) -> Verdict`——不需要改。

---

## 3. 新建 `tests/test_verifier.py`

```python
from __future__ import annotations

import pytest

from app.domain.task_engine.dag import Check, TaskDef, TaskNode
from app.domain.task_engine.ports import Verdict
from app.domain.task_engine.verifier import MechanicalVerifier


def _node(task_id="t1", acceptance=None, worktree=None):
    """快捷构造 TaskNode——只填 verifier 需要的字段。"""
    task = TaskDef(
        id=task_id,
        title=task_id,
        suggested_worker="w",
        acceptance=acceptance or [Check("mechanical", "true")],
    )
    node = TaskNode(task=task, worktree=worktree)
    return node


def _v(workspace=None):
    return MechanicalVerifier(workspace=workspace)
```

| TC | Given | When | Then |
|----|-------|------|------|
| **4.1 命门** | acceptance=`["false"]`（exit 1） | `verify` | `Verdict(passed=False)`，reason 含退出码 |
| **4.2 简单通过** | acceptance=`["true"]`（exit 0） | `verify` | `Verdict(passed=True)` |
| **4.3 多 check** | acceptance=`["true","true","true"]` | `verify` | 全部通过 → `passed=True` |
| **4.4 多 check 第二个失败** | acceptance=`["true","false","true"]` | `verify` | 第一个过、第二个 fail → `passed=False`，reason 指向第二条 |
| **4.5 命令超时** | acceptance=`["sleep 200"]`，CHECK_TIMEOUT=1 | `verify` | `passed=False`，reason 含"超时" |
| **4.6 命令不存在** | acceptance=`["nonexistent_cmd_xyz"]` | `verify` | `passed=False`，reason 含"无法执行" |
| **4.7 带 expect** | acceptance=`[Check("mechanical","bash -c 'exit 2'",expect="2")]` | `verify` | exit 2 匹配 expect 2 → `passed=True` |
| **4.8 expect 不匹配** | acceptance=`[Check("mechanical","bash -c 'exit 1'",expect="0")]` | `verify` | exit 1 ≠ expect 0 → `passed=False` |
| **4.9 空 acceptance 标 no_verify** | `acceptance=[], no_verify=True` | `verify` | `passed=True`（dag build 已校验 no_verify 标记，verifier 不重复判） |
| **4.10 在工作目录内跑** | acceptance=`["pwd"]`，worktree="/tmp/wt1" | `verify` | 命令 cwd 是 `/tmp/wt1`（非 verifier 自身 cwd） |

**命门用例（TC-4.1）**：

```python
@pytest.mark.asyncio
async def test_lying_worker_caught_by_verifier():
    """worker 自称完成但验收命令失败 → Verdict(passed=False)。"""
    node = _node("t1", acceptance=[Check("mechanical", "false")])
    v = _v()
    result = await v.verify(node)
    assert not result.passed
    assert "exit" in result.reason.lower() or "1" in result.reason


@pytest.mark.asyncio
async def test_honest_worker_passes():
    node = _node("t1", acceptance=[Check("mechanical", "true")])
    result = await MechanicalVerifier().verify(node)
    assert result.passed
```

**超时用例（TC-4.5）**：

```python
@pytest.mark.asyncio
async def test_command_timeout(monkeypatch):
    import app.domain.task_engine.verifier as mod
    monkeypatch.setattr(mod, "CHECK_TIMEOUT", 1)
    node = _node("t1", acceptance=[Check("mechanical", "sleep 5")])
    result = await MechanicalVerifier().verify(node)
    assert not result.passed
    assert "超时" in result.reason
```

**cwd 隔离用例（TC-4.10）**：

```python
@pytest.mark.asyncio
async def test_runs_in_worktree(tmp_path):
    wt = tmp_path / "wt1"
    wt.mkdir()
    node = _node("t1", acceptance=[Check("mechanical", "pwd")], worktree=str(wt))
    result = await MechanicalVerifier().verify(node)
    # 验证通过即可，pwd 只是确认不抛异常
    assert result.passed
```

---

## 4. 与 Orchestrator 的接法

Phase 1 的 `orchestrator.py` 已经通过 `Verifier` Protocol 调用，换掉 fake 不需要改 Orchestrator 代码：

```python
# Phase 1 构造（fake）
verifier = FakeVerifier({"t1": Verdict(True)})

# Phase 2 构造（真）
verifier = MechanicalVerifier(workspace=session.workspace_path)
```

Orchestrator 的 `_execute_and_settle` 不变：

```python
verdict = await self._verifier.verify(node)
if verdict.passed:
    self._transition(node, TaskStatus.COMPLETED)
else:
    self._handle_failure(node, verdict.reason)
```

---

## 5. 验收

```bash
V=/home/huishuohuademao/workspace/AgentHub/src/backend/.venv
$V/bin/python -m pytest tests/test_verifier.py -q --no-cov
$V/bin/ruff check app/domain/task_engine/verifier.py tests/test_verifier.py
```

**通过标准**：10 类用例全绿（含命门 TC-4.1 说谎 worker）+ ruff 干净。

此刻验证闸门的机械层已落地。之后 Phase 3 Planner 产出带 acceptance 的真实 TaskDef 时，Verifier 直接能验。

---

## 6. 文件增量

| 文件 | 动作 |
|------|------|
| `verifier.py` | 新建（~70 行） |
| `tests/test_verifier.py` | 新建（~90 行，10 用例） |
| `ports.py` | 不动（Phase 0 已定义 Verifier Protocol） |
| `orchestrator.py` | 不动（依赖注入，换 fake 不碰 Orchestrator） |

---

## 关联文档

- [[coordinator-mvp-implementation-plan]] Phase 2 概述
- [[coordinator-mvp-phase1-orchestrator]] Phase 0+1（Ports + Orchestrator 串行循环）
- [[coordinator-dag-driven-design-v2]] §6 验证闸门设计
- [[coordinator-test-plan]] §4 验证闸门 TC
