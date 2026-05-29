"""V2: 验证长驻进程内的对话记忆是否累积。

假设：第二条 user message 时 CLI 仍记得第一条对话内容。
"""

from __future__ import annotations

import asyncio

from _common import (
    read_until_result,
    send_user_message,
    spawn_cli,
    terminate,
    write_report,
)


async def main() -> None:
    notes: list[str] = []
    evidence: dict = {}

    handle = await spawn_cli(
        system_prompt="你是测试助手。回复必须极短（20 字内）。"
    )

    try:
        # 告知名字
        await send_user_message(handle, "请记住，我的名字叫张三丰。回复'好的'即可。")
        first = await read_until_result(handle, timeout=60.0)
        evidence["first_assistant_text"] = first["assistant_text"][:100]

        # 询问名字
        await send_user_message(handle, "我刚才告诉你我叫什么名字？")
        second = await read_until_result(handle, timeout=60.0)
        evidence["second_assistant_text"] = second["assistant_text"][:200]

        # 判定：第二条回复中是否包含"张三丰"
        contains_name = "张三丰" in second["assistant_text"]
        evidence["contains_name"] = contains_name

        if contains_name:
            notes.append("CLI 长驻进程在第二条消息时仍记得第一条提供的上下文")
            write_report("V2", passed=True, evidence=evidence, notes=notes)
        else:
            notes.append("CLI 未识别先前提供的名字，stream-json 模式可能不累积对话历史")
            write_report("V2", passed=False, evidence=evidence, notes=notes)

    finally:
        await terminate(handle)


if __name__ == "__main__":
    asyncio.run(main())
