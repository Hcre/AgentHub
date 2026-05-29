"""共享：spawn CLI、读 JSONL、超时管理。

被 v1/v2/v3/v4 验证脚本共用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("feasibility")


@dataclass
class CliHandle:
    proc: asyncio.subprocess.Process
    session_id: str
    stdout_buffer: list[str] = field(default_factory=list)


async def spawn_cli(
    *,
    system_prompt: str,
    session_id: str | None = None,
    extra_args: list[str] | None = None,
    model: str | None = None,
) -> CliHandle:
    """启动一个 CLI 子进程，使用 stream-json 双向格式。

    返回 handle 供后续 send / read 操作。
    """
    sid = session_id or str(uuid.uuid4())
    cmd: list[str] = [
        "claude",
        "--print",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--session-id",
        sid,
        "--system-prompt",
        system_prompt,
        "--permission-mode",
        "acceptEdits",
    ]
    if extra_args:
        cmd.extend(extra_args)

    env = os.environ.copy()
    if model:
        env["ANTHROPIC_MODEL"] = model

    logger.info("spawn: %s", " ".join(cmd[:8]) + " ...")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    return CliHandle(proc=proc, session_id=sid)


async def send_user_message(handle: CliHandle, content: str) -> None:
    """往 stdin 推送一条 user message JSONL。"""
    payload = {
        "type": "user",
        "message": {"role": "user", "content": content},
    }
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    logger.info("send  -> %s", content[:60])
    assert handle.proc.stdin is not None
    handle.proc.stdin.write(line.encode())
    await handle.proc.stdin.drain()


async def read_until_result(
    handle: CliHandle,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """读 stdout 直到出现 type=result 事件。返回 result 事件 + 累计 assistant 文本。

    超时则 raise TimeoutError。
    """
    assert handle.proc.stdout is not None
    assistant_text_chunks: list[str] = []
    deadline = asyncio.get_event_loop().time() + timeout

    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"未在 {timeout}s 内收到 result 事件")
        try:
            raw = await asyncio.wait_for(handle.proc.stdout.readline(), timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("readline 超时") from exc
        if not raw:
            raise RuntimeError(
                f"stdout 关闭 (returncode={handle.proc.returncode})"
            )
        line = raw.decode(errors="replace").strip()
        if not line:
            continue
        handle.stdout_buffer.append(line)
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("非 JSON 行: %s", line[:200])
            continue
        evt_type = data.get("type")
        if evt_type == "assistant":
            for block in data.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    assistant_text_chunks.append(block.get("text", ""))
        elif evt_type == "result":
            return {
                "result": data,
                "assistant_text": "".join(assistant_text_chunks),
            }


async def check_alive(handle: CliHandle) -> bool:
    """检查子进程是否仍 alive（returncode is None）。"""
    return handle.proc.returncode is None


async def terminate(handle: CliHandle) -> None:
    """优雅终止子进程。"""
    if handle.proc.returncode is None:
        try:
            assert handle.proc.stdin is not None
            handle.proc.stdin.close()
        except Exception:
            pass
        try:
            handle.proc.terminate()
            await asyncio.wait_for(handle.proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                handle.proc.kill()
            except ProcessLookupError:
                pass


async def drain_stderr(handle: CliHandle, max_bytes: int = 4000) -> str:
    """非阻塞读取已累积的 stderr。"""
    assert handle.proc.stderr is not None
    try:
        data = await asyncio.wait_for(handle.proc.stderr.read(max_bytes), timeout=0.5)
        return data.decode(errors="replace")
    except asyncio.TimeoutError:
        return ""


def write_report(test_id: str, passed: bool, evidence: dict, notes: list[str]) -> None:
    """打印结构化报告到 stdout。"""
    report = {
        "test_id": test_id,
        "passed": passed,
        "evidence": evidence,
        "notes": notes,
    }
    print("\n=== REPORT ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("=== END ===\n")
    sys.exit(0 if passed else 1)
