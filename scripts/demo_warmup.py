#!/usr/bin/env python
"""
AgentHub Demo 录制 v3 — 双阶段（warmup + demo），支持 ffmpeg 中途启动。

用法：
  python demo_warmup.py   # 启动 Chrome，加载 URL，等 5s，不退出
                          # 这时另一个终端可以启动 ffmpeg 录屏
  python demo_run.py      # 驱动现有 Chrome 走 5 个 story
"""
import asyncio
import time
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

URL = "http://127.0.0.1:5174"
CHROMIUM_PATH = r"C:\Users\yhn\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
WINDOW_X = 2560
WINDOW_Y = 0
VIEWPORT = {"width": 1920, "height": 1080}


async def warmup_then_idle():
    """启动 Chrome 到 DISPLAY6，导航到 URL，warmup 后无限等。"""
    print(f"[warmup] launch chromium @ ({WINDOW_X},{WINDOW_Y}) {VIEWPORT['width']}x{VIEWPORT['height']}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path=CHROMIUM_PATH,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                f"--window-position={WINDOW_X},{WINDOW_Y}",
                f"--window-size={VIEWPORT['width']},{VIEWPORT['height']}",
            ],
        )
        ctx = await browser.new_context(
            viewport=VIEWPORT,
            locale="zh-CN",
            device_scale_factor=1,
        )
        page = await ctx.new_page()

        print("[warmup] navigate")
        await page.goto(URL, wait_until="domcontentloaded", timeout=10000)
        try:
            await page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)
        # 截一张图放到 dbg 目录
        out_dir = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video\_dbg")
        out_dir.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(out_dir / "warmup-final.png"))
        print(f"[warmup] ready. screenshot @ {out_dir/'warmup-final.png'}")
        print("[warmup] >>> WAITING for demo to drive this browser. Do not close.")
        # 一直等直到外部 kill
        try:
            while True:
                await page.wait_for_timeout(5000)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            print("[warmup] cleanup")
            try:
                await ctx.close()
                await browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(warmup_then_idle())
    except KeyboardInterrupt:
        print("interrupted")
