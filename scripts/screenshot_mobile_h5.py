"""
P2-5 移动端 H5 截图脚本：playwright 跑 2 张 (mobile 375 + desktop 1280)。
输出：docs/deliverables/screenshots/mobile-h5-{viewport}.png
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:5174"
OUT_DIR = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\screenshots")

VIEWPORTS = [
    ("mobile-375", 375, 812),  # iPhone 13
    ("desktop-1280", 1280, 800),  # 桌面
]


async def shot_one(p, name, w, h):
    print(f"[shot] {name} @ {w}x{h}")
    browser = await p.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": w, "height": h}, locale="zh-CN")
    page = await ctx.new_page()
    try:
        await page.goto(URL, wait_until="domcontentloaded", timeout=15000)
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        out = OUT_DIR / f"mobile-h5-{name}.png"
        await page.screenshot(path=str(out), full_page=False)
        print(f"  saved → {out}")
    finally:
        await ctx.close()
        await browser.close()


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        for name, w, h in VIEWPORTS:
            try:
                await shot_one(p, name, w, h)
            except Exception as e:
                print(f"  !! {name} failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
