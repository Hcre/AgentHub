"""V3: 验证 --system-prompt 在多轮 user message 之间是否持续生效。

假设：首次 spawn 注入的 system_prompt 在 5 条 user 消息后仍生效。
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


REQUIRED_PREFIX = "[测试助手]"

SYSTEM_PROMPT = (
    "你是「测试助手」。这是硬性规则：每次回复的开头**必须**写「[测试助手]」"
    "（包含中括号、严格匹配），然后再写其他内容。回复必须简短（20 字内）。"
)

PROMPTS = [
    "你好",
    "今天天气怎么样",
    "1 + 1 等于几",
    "推荐一本书",
    "再见",
]


async def main() -> None:
    notes: list[str] = []
    evidence: dict = {"replies": []}

    handle = await spawn_cli(system_prompt=SYSTEM_PROMPT)

    try:
        hit = 0
        for i, prompt in enumerate(PROMPTS, 1):
            await send_user_message(handle, prompt)
            r = await read_until_result(handle, timeout=60.0)
            text = r["assistant_text"]
            ok = text.lstrip().startswith(REQUIRED_PREFIX)
            evidence["replies"].append({
                "turn": i,
                "prompt": prompt,
                "reply_head": text[:80],
                "prefix_present": ok,
            })
            if ok:
                hit += 1

        evidence["hit_rate"] = f"{hit}/{len(PROMPTS)}"

        if hit == len(PROMPTS):
            notes.append("system_prompt 在 5 轮中全部生效")
            write_report("V3", passed=True, evidence=evidence, notes=notes)
        elif hit >= 3:
            notes.append(
                f"system_prompt 部分生效 ({hit}/{len(PROMPTS)})，可能需要 reminder 注入"
            )
            write_report("V3", passed=False, evidence=evidence, notes=notes)
        else:
            notes.append(
                f"system_prompt 显著衰减 ({hit}/{len(PROMPTS)})，长驻模式下需要每轮 reminder"
            )
            write_report("V3", passed=False, evidence=evidence, notes=notes)

    finally:
        await terminate(handle)


if __name__ == "__main__":
    asyncio.run(main())
