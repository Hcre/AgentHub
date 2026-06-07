#!/usr/bin/env python
"""
Master orchestrator: 串行调度 warmup + ffmpeg + demo_run。

不依赖 PowerShell，纯 Python 进程管理。
"""
import os
import sys
import time
import subprocess
from pathlib import Path

VIDEO_DIR = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video")
PROJECT_ROOT = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub")
PYTHON = sys.executable
WARMUP = PROJECT_ROOT / "scripts" / "demo_warmup.py"
DEMO = PROJECT_ROOT / "scripts" / "demo_run.py"
RECORDING = VIDEO_DIR / "raw-recording.mp4"
FFMPEG_OFFSET_X = 2560
FFMPEG_OFFSET_Y = 0
FFMPEG_SIZE_W = 1920
FFMPEG_SIZE_H = 1080
FFMPEG_DURATION = 200


def start_warmup():
    print(f"[orch] start warmup: {WARMUP}")
    p = subprocess.Popen(
        [PYTHON, str(WARMUP)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    return p


def start_ffmpeg():
    ffmpeg = "ffmpeg.exe"
    args = [
        ffmpeg, "-y",
        "-f", "gdigrab",
        "-framerate", "30",
        "-offset_x", str(FFMPEG_OFFSET_X),
        "-offset_y", str(FFMPEG_OFFSET_Y),
        "-video_size", f"{FFMPEG_SIZE_W}x{FFMPEG_SIZE_H}",
        "-i", "desktop",
        "-t", str(FFMPEG_DURATION),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        str(RECORDING),
    ]
    print(f"[orch] start ffmpeg: {' '.join(args)}")
    p = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return p


def run_demo():
    print(f"[orch] start demo: {DEMO}")
    p = subprocess.Popen(
        [PYTHON, str(DEMO)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return p


def main():
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    # 旧文件清掉
    for f in VIDEO_DIR.glob("raw-recording*.mp4"):
        f.unlink()
    for f in VIDEO_DIR.glob("frame-*.png"):
        f.unlink()

    print("[orch] === step 1: start warmup ===")
    warmup = start_warmup()
    # 等 warmup 打印 "ready" 标记（最多 30s）
    ready = False
    start = time.time()
    while time.time() - start < 30:
        if warmup.poll() is not None:
            print("[orch] !! warmup died early")
            out, _ = warmup.communicate()
            print(out)
            sys.exit(1)
        line = warmup.stdout.readline()
        if line:
            print(f"  warmup: {line.rstrip()}")
            if "ready" in line.lower() or "warming up" in line.lower() or "waiting" in line.lower():
                ready = True
                break
        time.sleep(0.1)
    if not ready:
        print("[orch] warmup did not signal ready in 30s, but assume ok after 10s")
        time.sleep(2)

    print("[orch] === step 2: start ffmpeg ===")
    ffmpeg = start_ffmpeg()
    time.sleep(2)  # ffmpeg 启动需要 1-2s

    print("[orch] === step 3: start demo ===")
    demo = run_demo()
    # 流式输出
    while demo.poll() is None:
        line = demo.stdout.readline()
        if line:
            print(f"  demo: {line.rstrip()}")
        time.sleep(0.05)
    out, _ = demo.communicate()
    print(f"  demo final: {out[-500:]}")

    print("[orch] === step 4: wait for ffmpeg to finish ===")
    # ffmpeg 录 200s，可能 demo 跑完时还在录
    while ffmpeg.poll() is None:
        time.sleep(1)
    print(f"  ffmpeg done, return code: {ffmpeg.returncode}")

    # 等等 warmup 输出
    time.sleep(2)
    print("[orch] === step 5: kill warmup ===")
    try:
        warmup.terminate()
        time.sleep(1)
        if warmup.poll() is None:
            warmup.kill()
    except Exception:
        pass

    print("[orch] === step 6: verify ===")
    if RECORDING.exists():
        size_mb = RECORDING.stat().st_size / 1024 / 1024
        print(f"  recording: {RECORDING} ({size_mb:.1f} MB)")
    else:
        print(f"  !! recording not found: {RECORDING}")
        sys.exit(1)


if __name__ == "__main__":
    main()
