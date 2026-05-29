"""V5: 验证 --resume + --input-format stream-json 崩溃恢复兼容性。

假设：
- CLI 用 --session-id <key> 首次 spawn 后，会话写入 ~/.claude/sessions/<key>/
- kill 进程后，用 --resume <key> + --input-format stream-json 重连
- 重连后 CLI 应记住之前的 conversation turn（包括 assistant 回复）

失败后果：
- Phase 1 crash recovery 无法依赖 --resume，需自实现"补灌历史"机制
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import uuid

from _common import (
    CliHandle,
    check_alive,
    drain_stderr,
    read_until_result,
    send_user_message,
    spawn_cli,
    terminate,
    write_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("feasibility.v5")


async def spawn_resume(session_id: str) -> CliHandle:
    """用 --resume 重连已有会话（不带 --session-id，冲突）。"""
    cmd: list[str] = [
        "claude",
        "--print",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--resume", session_id,
        "--permission-mode", "acceptEdits",
    ]
    env = os.environ.copy()
    logger.info("spawn resume: %s", " ".join(cmd[:6]) + f" --resume {session_id}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    return CliHandle(proc=proc, session_id=session_id)


async def test_resume_recovery() -> dict:
    """核心测试：spawn → 对话 → kill → resume → 验证历史保留。"""
    session_id = str(uuid.uuid4())
    evidence: dict = {"session_id": session_id}
    notes: list[str] = []

    # ── Phase 1: 首次 spawn + 建立对话 ──
    logger.info("=== Phase 1: 首次 spawn ===")
    handle1 = await spawn_cli(
        system_prompt=(
            "你是 Alice，一个技术助手。"
            "记住用户告诉你的所有信息，之后会被问到。"
        ),
        session_id=session_id,
    )
    try:
        # 建立一段有辨识度的对话
        await send_user_message(
            handle1,
            "我叫 Bob，请记住：我的代号是 BLUE42，我最喜欢的颜色是绿色。"
            "请用一句话确认你记住了。",
        )
        result1 = await read_until_result(handle1, timeout=60.0)
        evidence["turn1_response"] = result1["assistant_text"][:200]
        evidence["turn1_complete"] = "result" in result1

        # 验证是否记住了
        await send_user_message(handle1, "我叫什么名字？代号是什么？")
        result1b = await read_until_result(handle1, timeout=60.0)
        evidence["turn2_response"] = result1b["assistant_text"][:200]
        evidence["turn2_remembers"] = (
            "BOB" in result1b["assistant_text"].upper()
            and "BLUE42" in result1b["assistant_text"].upper()
        )

        if not evidence["turn2_remembers"]:
            notes.append("Phase 1 未记住信息，后续 resume 验证无意义")
            return evidence

        # ── Phase 2: kill 进程 ──
        logger.info("=== Phase 2: kill 进程 ===")
        pid = handle1.proc.pid
        evidence["pid"] = pid
        os.kill(pid, signal.SIGKILL)
        await asyncio.sleep(1.0)

        alive_after_kill = await check_alive(handle1)
        evidence["alive_after_kill"] = alive_after_kill
        evidence["returncode_after_kill"] = handle1.proc.returncode

        # ── Phase 3: --resume 重连 ──
        logger.info("=== Phase 3: --resume 重连 ===")
        await terminate(handle1)  # 清理旧的 handle

        handle2 = await spawn_resume(session_id)
        evidence["resume_spawned"] = await check_alive(handle2)
    finally:
        # handle1 might be dead already, terminate is idempotent
        await terminate(handle1)

    try:
        # 不发 system_prompt 直接问之前的内容
        # 如果 --resume 有效，CLI 应记得 Alice 身份和用户信息
        await send_user_message(handle2, "我刚才叫什么名字？代号和最喜欢的颜色是什么？")

        result2 = await read_until_result(handle2, timeout=60.0)
        evidence["resume_response"] = result2["assistant_text"][:300]
        text_upper = result2["assistant_text"].upper()

        evidence["resume_remembers_name"] = "BOB" in text_upper
        evidence["resume_remembers_code"] = "BLUE42" in text_upper
        evidence["resume_remembers_color"] = "绿色" in result2["assistant_text"] or "GREEN" in text_upper

        # 也要检查 system_prompt（Alice 身份）是否保留
        # 如果 CLI 不知道自己是 Alice，说明 --resume 未恢复 system_prompt
        evidence["resume_remembers_identity"] = "ALICE" in text_upper or "助手" in result2["assistant_text"]

        # 综合判定
        passed = (
            evidence["resume_remembers_name"]
            and evidence["resume_remembers_code"]
        )
        evidence["passed"] = passed

        if not passed:
            notes.append(
                "--resume 未恢复对话历史，崩溃恢复需要自实现「补灌历史」机制"
            )
        else:
            notes.append(
                "--resume + stream-json 可恢复历史，crash recovery 可用此路径"
            )

        if not evidence["resume_remembers_identity"]:
            notes.append("额外发现：--resume 未恢复 system_prompt / Agent 身份")

        stderr = await drain_stderr(handle2)
        if stderr:
            evidence["stderr_tail"] = stderr[-500:]

        return evidence

    finally:
        await terminate(handle2)


async def main() -> None:
    notes: list[str] = []
    evidence: dict = {}

    evidence["resume_test"] = await test_resume_recovery()

    rt = evidence["resume_test"]
    passed = rt.get("passed", False)

    if passed:
        notes.append(
            "--resume + stream-json 恢复成功，crash recovery 方案可行"
        )
        write_report("V5", passed=True, evidence=evidence, notes=notes)
    else:
        notes.append(
            "--resume + stream-json 无法恢复历史，"
            "Phase 1 需自实现「补灌历史」或放弃长驻改为每次 --resume 重连"
        )
        write_report("V5", passed=False, evidence=evidence, notes=notes)


if __name__ == "__main__":
    asyncio.run(main())
