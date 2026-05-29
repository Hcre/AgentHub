"""V1: 验证 CLI 在收到一条 user 消息处理完后是否保持 stdin 监听。

假设：进程在输出 type=result 后不退出，继续等待 stdin 下一条 JSONL。
"""

from __future__ import annotations

import asyncio
import time

from _common import (
    check_alive,
    drain_stderr,
    read_until_result,
    send_user_message,
    spawn_cli,
    terminate,
    write_report,
)


async def main() -> None:
    notes: list[str] = []
    evidence: dict = {}

    handle = await spawn_cli(system_prompt="你是测试助手，回复必须简短（10 字以内）")
    t0 = time.monotonic()

    try:
        # 第一条消息
        await send_user_message(handle, "说 hello")
        first = await read_until_result(handle, timeout=60.0)
        evidence["first_result_received_ms"] = int((time.monotonic() - t0) * 1000)
        evidence["first_assistant_text"] = first["assistant_text"][:100]

        # 等 3 秒后检查进程状态
        await asyncio.sleep(3.0)
        still_alive = await check_alive(handle)
        evidence["alive_3s_after_first_result"] = still_alive
        evidence["returncode_after_3s"] = handle.proc.returncode

        if not still_alive:
            notes.append("进程在第一条 result 后 3 秒内退出，长驻不成立")
            stderr = await drain_stderr(handle)
            if stderr:
                evidence["stderr_tail"] = stderr[-500:]
            write_report("V1", passed=False, evidence=evidence, notes=notes)
            return

        # 第二条消息
        t1 = time.monotonic()
        try:
            await send_user_message(handle, "说 world")
        except (BrokenPipeError, ConnectionResetError) as exc:
            notes.append(f"写入第二条时 stdin 断开: {type(exc).__name__}")
            evidence["second_write_error"] = type(exc).__name__
            write_report("V1", passed=False, evidence=evidence, notes=notes)
            return

        try:
            second = await read_until_result(handle, timeout=60.0)
        except (TimeoutError, RuntimeError) as exc:
            notes.append(f"等待第二条 result 失败: {exc}")
            evidence["second_read_error"] = str(exc)
            write_report("V1", passed=False, evidence=evidence, notes=notes)
            return

        evidence["second_result_received_ms"] = int((time.monotonic() - t1) * 1000)
        evidence["second_assistant_text"] = second["assistant_text"][:100]

        passed = bool(second["assistant_text"])
        if not passed:
            notes.append("第二条 result 返回但 assistant_text 为空")
        else:
            notes.append("CLI 在第一条 result 后保持长驻并响应第二条 user message")

        write_report("V1", passed=passed, evidence=evidence, notes=notes)

    finally:
        await terminate(handle)


if __name__ == "__main__":
    asyncio.run(main())
