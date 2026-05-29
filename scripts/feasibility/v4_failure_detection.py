"""V4: 验证异常退出与 stderr 捕获机制。

假设：
- 子进程被 kill 后，父端再次写 stdin 能捕获到 BrokenPipeError 或 returncode
- 发送格式错误的 JSONL 时 CLI 退出/报错可被检测
"""

from __future__ import annotations

import asyncio
import os
import signal

from _common import (
    check_alive,
    drain_stderr,
    read_until_result,
    send_user_message,
    spawn_cli,
    terminate,
    write_report,
)


async def test_kill_detection() -> dict:
    """启动 → 推送一条 → 等 result → SIGKILL → 再次推送看是否抛错。"""
    handle = await spawn_cli(system_prompt="测试助手，简短回复")
    evidence: dict = {}
    try:
        await send_user_message(handle, "hi")
        await read_until_result(handle, timeout=60.0)

        pid = handle.proc.pid
        evidence["pid"] = pid
        os.kill(pid, signal.SIGKILL)
        await asyncio.sleep(1.0)

        alive_after_kill = await check_alive(handle)
        evidence["alive_after_kill"] = alive_after_kill
        evidence["returncode_after_kill"] = handle.proc.returncode

        # 尝试再次写入
        write_error: str | None = None
        try:
            await send_user_message(handle, "still there?")
        except (BrokenPipeError, ConnectionResetError, AssertionError) as exc:
            write_error = type(exc).__name__
        except Exception as exc:
            write_error = f"OTHER:{type(exc).__name__}"

        evidence["write_after_kill_error"] = write_error
        return evidence
    finally:
        await terminate(handle)


async def test_bad_jsonl() -> dict:
    """发送格式错误 JSONL，观察 CLI 反应。"""
    handle = await spawn_cli(system_prompt="测试助手，简短回复")
    evidence: dict = {}
    try:
        assert handle.proc.stdin is not None
        handle.proc.stdin.write(b"{not json}\n")
        await handle.proc.stdin.drain()
        await asyncio.sleep(3.0)

        alive = await check_alive(handle)
        evidence["alive_after_bad_jsonl"] = alive
        evidence["returncode"] = handle.proc.returncode

        stderr = await drain_stderr(handle)
        if stderr:
            evidence["stderr_tail"] = stderr[-300:]
        return evidence
    finally:
        await terminate(handle)


async def main() -> None:
    notes: list[str] = []
    evidence: dict = {}

    evidence["kill_test"] = await test_kill_detection()
    evidence["bad_jsonl_test"] = await test_bad_jsonl()

    # 判定
    kill_detected = (
        not evidence["kill_test"]["alive_after_kill"]
        and evidence["kill_test"]["write_after_kill_error"] is not None
    )
    bad_jsonl_handled = (
        # CLI 要么退出，要么 stderr 有提示
        not evidence["bad_jsonl_test"]["alive_after_bad_jsonl"]
        or "stderr_tail" in evidence["bad_jsonl_test"]
    )

    evidence["kill_detected"] = kill_detected
    evidence["bad_jsonl_handled"] = bad_jsonl_handled

    if kill_detected and bad_jsonl_handled:
        notes.append("kill 与坏 JSONL 均可检测")
        write_report("V4", passed=True, evidence=evidence, notes=notes)
    else:
        if not kill_detected:
            notes.append("kill 后写 stdin 未抛错，需要 watchdog 心跳")
        if not bad_jsonl_handled:
            notes.append("坏 JSONL 既不退出也无 stderr，CLI 容错过度可能掩盖问题")
        write_report("V4", passed=False, evidence=evidence, notes=notes)


if __name__ == "__main__":
    asyncio.run(main())
