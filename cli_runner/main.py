"""CLI Runner — 宿主机常驻进程。

启动: python cli_runner/main.py --backend ws://localhost:8000
依赖: pip install websockets

职责:
    1. 连接 AgentHub Backend WebSocket (/ws/runner)
    2. 接收执行指令 {binary, args, cwd, prompt, env}
    3. 启动 CLI 子进程 (cwd = workspace)
    4. 逐行读取 stdout JSON 并流式回传
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import websockets
from websockets.asyncio.client import connect

RECONNECT_DELAY = 5
HOSTNAME = os.environ.get("COMPUTERNAME", "unknown")


async def execute(ws, msg: dict) -> None:
    """执行一次 CLI 调用。"""
    rid = msg["request_id"]
    binary = msg["binary"]
    args = msg.get("args", [])
    cwd = msg.get("cwd", "")
    prompt = msg.get("prompt", "")
    env_extra = msg.get("env", {})

    # 校验 workspace
    ws_dir = Path(cwd) if cwd else None
    if ws_dir and not ws_dir.exists():
        await ws.send(json.dumps({"type": "error", "request_id": rid,
                                  "error": f"目录不存在: {cwd}"}))
        return

    cmd = [binary] + args
    env = os.environ.copy()
    env.update(env_extra)

    print(f"[runner] exec: {' '.join(cmd)} (cwd={cwd})")
    t0 = time.time()

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd or None,
            env=env,
            text=True,
        )
    except FileNotFoundError:
        await ws.send(json.dumps({"type": "error", "request_id": rid,
                                  "error": f"未找到命令: {binary}"}))
        return

    if proc.stdin:
        proc.stdin.write(prompt)
        proc.stdin.flush()
        proc.stdin.close()

    seq = 0
    if proc.stdout:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"type": "text", "content": line}
            await ws.send(json.dumps({
                "type": "stream", "request_id": rid,
                "seq": seq, "event": event,
            }))
            seq += 1

    proc.wait()
    elapsed = time.time() - t0

    stderr_text = ""
    if proc.stderr:
        stderr_text = proc.stderr.read()[:1000]

    print(f"[runner] done: exit={proc.returncode} time={elapsed:.1f}s")
    await ws.send(json.dumps({
        "type": "done", "request_id": rid,
        "exit_code": proc.returncode,
        "elapsed_ms": int(elapsed * 1000),
        "stderr": stderr_text,
    }))


async def run_loop(backend_url: str) -> None:
    """连接 Backend /ws/runner，等待指令。"""
    ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = ws_url.rstrip("/") + "/ws/runner"

    while True:
        try:
            print(f"[runner] 连接 {ws_url} ...")
            async with connect(ws_url, ping_interval=20) as ws:
                await ws.send(json.dumps({"type": "hello", "runner_id": f"runner-{HOSTNAME}"}))
                ack = await ws.recv()
                print(f"[runner] 已连接: {ack}", flush=True)

                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=600)
                    except asyncio.TimeoutError:
                        continue
                    msg = json.loads(raw)
                    if msg.get("type") == "exec":
                        await execute(ws, msg)
                    elif msg.get("type") == "pong":
                        pass
        except Exception as exc:
            print(f"[runner] 断开: {exc}，{RECONNECT_DELAY}s 后重连...", flush=True)
            await asyncio.sleep(RECONNECT_DELAY)


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentHub CLI Runner")
    parser.add_argument("--backend", default="http://localhost:8000")
    args = parser.parse_args()

    print(f"[runner] AgentHub CLI Runner (host={HOSTNAME})")
    asyncio.run(run_loop(args.backend))


if __name__ == "__main__":
    main()
