"""Verifier — 机械验收闸门（coordinator-dag-driven-design-v2 §6.2 机械层）。

MVP：只跑 mechanical check，挨个执行 acceptance 命令，抓退出码。
非 mechanical（llm_judge/human）在 MVP **fail-closed**——不静默通过（§6.1）。
标准档：加 reviewer agent (llm_judge) + human 闸门 + 集成验证。

⚠️ 安全（信任边界）：check.spec 是 Planner(LLM) 生成的 shell 命令，在 worker 工作目录里
   执行。被 prompt 注入的设计文档可能注入恶意命令（如 rm -rf）。当前缓解：
   - MVP：workspace 是受信项目目录 + 依赖 Planner prompt 约束 + 人工 plan review。
   - 标准档：每 task 独立 worktree 隔离，限制可达范围。
   后续可加命令 allowlist / 沙箱。落地真实环境前需复核此边界。
"""

from __future__ import annotations

import asyncio
import logging

from app.domain.task_engine.dag import Check, TaskNode
from app.domain.task_engine.ports import Verdict

logger = logging.getLogger(__name__)

# 单命令最长执行时间（秒），防 acceptance 里写了死循环
CHECK_TIMEOUT = 120


class MechanicalVerifier:
    """机械验收器：跑命令 → 读退出码 → 出裁决。无状态。"""

    def __init__(self, workspace: str | None = None) -> None:
        # MVP 串行无 worktree：所有 worker 共用 workspace。
        # 标准档：每个 task 有独立 worktree（node.worktree 覆盖）。
        self._fallback_workspace = workspace

    async def verify(self, node: TaskNode) -> Verdict:
        """按 TaskDef.acceptance 逐个跑 mechanical check。第一个失败即停。"""
        if node.task.no_verify:
            return Verdict(passed=True, reason="no_verify：显式声明无需验证")

        cwd = node.worktree or self._fallback_workspace
        if cwd is None:
            # 无工作目录 → 拒绝在后端 server cwd 跑任意命令（安全 + 正确性）
            return Verdict(
                passed=False,
                reason="Verifier 缺工作目录：node.worktree 与 workspace 均为空",
            )

        if not node.task.acceptance:
            # build_graph 应已拦截（空 acceptance 且非 no_verify）；防御性 fail-closed
            return Verdict(passed=False, reason="无 acceptance 且未标 no_verify")

        for check in node.task.acceptance:
            if check.kind != "mechanical":
                # MVP fail-closed：不静默通过未支持的 check（§6.1）。
                # Phase 3 Planner 须只产 mechanical；此处为防御性兜底。
                logger.warning(
                    "MVP Verifier 收到 %s check（task=%s）→ fail-closed",
                    check.kind, node.task.id,
                )
                return Verdict(
                    passed=False,
                    reason=f"MVP 不支持 {check.kind} 验收（需 Planner 只产 mechanical）",
                )
            result = await self._run_check(check, cwd)
            if not result.passed:
                return result

        return Verdict(passed=True)

    async def _run_check(self, check: Check, cwd: str) -> Verdict:
        """执行单条机械验收命令，比对退出码。"""
        logger.debug("Verifier running: %s (cwd=%s)", check.spec, cwd)

        try:
            proc = await asyncio.create_subprocess_shell(
                check.spec,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return Verdict(
                passed=False, reason=f"验收命令无法执行: {check.spec} ({exc})"
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CHECK_TIMEOUT
            )
        except TimeoutError:
            proc.kill()  # 杀残留进程，回收避免僵尸 + "Event loop is closed"
            await proc.wait()
            return Verdict(
                passed=False, reason=f"验收命令超时（>{CHECK_TIMEOUT}s）: {check.spec}"
            )

        exit_code = proc.returncode
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        expected = 0
        if check.expect is not None:
            try:
                expected = int(check.expect)
            except ValueError:
                return Verdict(
                    passed=False,
                    reason=f"无效 expect（需整数退出码）: {check.expect!r}",
                )

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

        return Verdict(passed=True)
