#!/usr/bin/env python
"""
AgentHub Demo 录制 v6 — 解决 v4 wallpaper 残留 + v5 SetWindowPos crash。

关键改进（vs v5）：
  1. ❌ 去掉 Win32 SetWindowPos（v5 crash 元凶，触发 Windows DPI 重排）
  2. ✅ Chrome 启动用 --start-maximized（一启动就占满主屏，taskbar drag 无 fallback）
  3. ✅ ffmpeg 显式 -offset_x 0 -offset_y 0 -video_size 1920x1080（录主屏 logical 像素）
  4. ✅ warmup + ffmpeg + demo 流程单脚本同步编排（避免 v4 双进程时序错位）
  5. ✅ 新录到 raw-recording-v6.mp4，不覆盖 v4 备份

已知约束：
  - Windows 11 主屏物理 1707x1067, logical 1920x1080 (125% 缩放)
  - ffmpeg gdigrab 捕获 logical 像素（1920x1080）
  - Chrome viewport=1920x1080 + window-position=0,0 + --start-maximized → 占满主屏
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page

# --- Config ---
URL = "http://127.0.0.1:5174"
CHROMIUM_PATH = r"C:\Users\yhn\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
FFMPEG_W = 1920
FFMPEG_H = 1080
FFMPEG_DURATION = 200

VIDEO_DIR = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video")
DBG_DIR = VIDEO_DIR / "_dbg"
RECORDING = VIDEO_DIR / "raw-recording-v6.mp4"

# v6: --start-maximized 是关键，--window-size 给个 fallback 默认
CHROME_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-blink-features=AutomationControlled",
    "--start-maximized",  # 关键：启动即最大化
    "--window-position=0,0",
    "--window-size=1920,1080",
]


# --- Playwright helpers (from v5) ---

async def settle(page: Page, ms: int = 600):
    await page.wait_for_timeout(ms)


async def click_text(page: Page, text: str, timeout_ms: int = 2500):
    loc = page.get_by_text(text, exact=False).first
    try:
        await loc.scroll_into_view_if_needed(timeout=1000)
    except Exception:
        pass
    try:
        await loc.click(timeout=timeout_ms)
        return True
    except Exception as e:
        print(f"  click '{text}': {type(e).__name__}: {str(e)[:80]}")
        return False


async def hover_text(page: Page, text: str, timeout_ms: int = 1500):
    loc = page.get_by_text(text, exact=False).first
    try:
        await loc.hover(timeout=timeout_ms)
        return True
    except Exception:
        return False


async def click_role(page: Page, role: str, name: str, timeout_ms: int = 2500):
    loc = page.get_by_role(role, name=name).first
    try:
        await loc.click(timeout=timeout_ms)
        return True
    except Exception as e:
        print(f"  click role={role} name='{name}': {type(e).__name__}")
        return False


async def debug_shot(page: Page, label: str):
    try:
        await page.screenshot(path=str(DBG_DIR / f"dbg-v6-{label}.png"), full_page=False)
    except Exception:
        pass


# --- 5 stories + opening + close (from v5) ---

async def section0_opening(page: Page):
    print("[0:00] section 0 opening")
    nav = page.locator("aside[aria-label] nav button")
    n = await nav.count()
    for i in range(n):
        try:
            await nav.nth(i).hover()
        except Exception:
            pass
        await settle(page, 350)
    await settle(page, 1500)
    await debug_shot(page, "00-opening")


async def section1_s1(page: Page):
    print("[0:15] section 1 S1")
    await click_text(page, "对话 2", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "01-conv")
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 600)

    await hover_text(page, "复制代码", timeout_ms=1500)
    await settle(page, 800)
    await click_role(page, "button", "复制代码", timeout_ms=1500)
    await settle(page, 1500)
    await debug_shot(page, "01-copied")

    await hover_text(page, "Pin", timeout_ms=1500)
    await settle(page, 800)


async def section2_s2(page: Page):
    print("[0:45] section 2 S2")
    nav = page.locator("aside[aria-label] nav button")
    try:
        await nav.nth(2).click(timeout=2500)
    except Exception as e:
        print(f"  group nav: {e}")
    await settle(page, 1500)
    await debug_shot(page, "02-groups")

    await click_text(page, "S2 - 营销页升级", timeout_ms=2500)
    await settle(page, 2000)
    await debug_shot(page, "02-group")

    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 1500)

    try:
        composer = page.locator("textarea").last
        await composer.click()
        await composer.fill("@Coordinator 帮我把 S2 进度同步给老板")
        await settle(page, 2000)
    except Exception as e:
        print(f"  composer: {e}")
    await debug_shot(page, "02-typed")


async def section3_s3(page: Page):
    print("[1:15] section 3 S3 inline preview")
    btns = page.locator("button[title*='右侧面板']")
    if await btns.count() > 0:
        try:
            await btns.first.click(timeout=2500)
        except Exception as e:
            print(f"  toggle: {e}")
    await settle(page, 1500)
    await debug_shot(page, "03-panel")

    for t in ["项目文件", "审查 diff", "部署", "网页"]:
        await hover_text(page, t, timeout_ms=1500)
        await settle(page, 500)

    await click_text(page, "项目文件", timeout_ms=2000)
    await settle(page, 1500)
    await debug_shot(page, "03-files")

    await hover_text(page, "审查 diff", timeout_ms=1500)
    await settle(page, 1200)
    await debug_shot(page, "03-diff-mode")


async def section4_s4(page: Page):
    print("[1:45] section 4 S4 create agent")
    btns = page.locator("button[title*='右侧面板']")
    if await btns.count() > 0:
        try:
            await btns.first.click()
        except Exception:
            pass
    await settle(page, 600)

    nav = page.locator("aside[aria-label] nav button")
    try:
        await nav.nth(1).click()
    except Exception as e:
        print(f"  AI nav: {e}")
    await settle(page, 1500)
    await debug_shot(page, "04-agents")

    await click_text(page, "创建队友", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "04-modal")

    try:
        modal = page.locator("[role='dialog']").first
        if await modal.count() > 0:
            engineer = modal.locator("text=工程师").first
            await engineer.click(timeout=2500)
        else:
            await click_text(page, "工程师", timeout_ms=2500)
    except Exception as e:
        print(f"  engineer click: {e}")
    await settle(page, 1000)
    await debug_shot(page, "04-template")

    try:
        await click_text(page, "Claude Code", timeout_ms=2500)
    except Exception as e:
        print(f"  claude code: {e}")
    await settle(page, 1500)
    await debug_shot(page, "04-cli")

    try:
        for label in ["名字", "名称"]:
            loc = page.get_by_label(label, exact=False).first
            if await loc.count() > 0:
                await loc.fill("试水 Bot")
                break
    except Exception:
        pass
    await settle(page, 800)

    if not await click_text(page, "创建", timeout_ms=1500):
        print("  WARN: no '创建' button found")
    await settle(page, 2000)
    await debug_shot(page, "04-after-create")


async def section5_s5(page: Page):
    print("[2:15] section 5 S5 tasks + inbox")
    try:
        cancel = page.get_by_role("button", name="取消").first
        if await cancel.count() > 0:
            await cancel.click()
    except Exception:
        pass
    await settle(page, 600)

    nav = page.locator("aside[aria-label] nav button")
    try:
        await nav.nth(0).click()
    except Exception:
        pass
    await settle(page, 1200)

    await click_text(page, "Claude", timeout_ms=2500)
    await settle(page, 1200)
    await debug_shot(page, "05-claude")

    await click_text(page, "任务", timeout_ms=2500)
    await settle(page, 2000)
    await debug_shot(page, "05-kanban")

    try:
        await page.get_by_role("button", name="list", exact=False).first.hover()
        await settle(page, 400)
        await page.get_by_role("button", name="list", exact=False).first.click()
    except Exception as e:
        print(f"  list: {e}")
    await settle(page, 1200)
    await debug_shot(page, "05-list")

    try:
        await page.get_by_role("button", name="grid", exact=False).first.click()
    except Exception as e:
        print(f"  grid: {e}")
    await settle(page, 1200)
    await debug_shot(page, "05-final")


async def section6_close(page: Page):
    print("[2:45] section 6 closing")
    theme = page.locator("button[aria-label*='主题']").first
    for _ in range(3):
        try:
            if await theme.count() > 0:
                await theme.click()
        except Exception:
            pass
        await settle(page, 700)
    await settle(page, 1500)
    await debug_shot(page, "06-close")


# --- ffmpeg orchestration (v6: 显式 offset 0 0, video_size 1920x1080) ---

def start_ffmpeg():
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    if RECORDING.exists():
        RECORDING.unlink()
    args = [
        "ffmpeg.exe", "-y",
        "-f", "gdigrab",
        "-framerate", "30",
        "-offset_x", "0",
        "-offset_y", "0",
        "-video_size", f"{FFMPEG_W}x{FFMPEG_H}",
        "-i", "desktop",
        "-t", str(FFMPEG_DURATION),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-loglevel", "error",
        str(RECORDING),
    ]
    print(f"[orch] ffmpeg: {' '.join(args)}")
    p = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return p


def wait_ffmpeg(p, timeout=240):
    print(f"[orch] wait ffmpeg (PID={p.pid})...")
    start = time.time()
    while p.poll() is None:
        time.sleep(2)
        if time.time() - start > timeout:
            print("[orch] ffmpeg timeout, kill")
            p.kill()
            return False
    print(f"[orch] ffmpeg done, rc={p.returncode}")
    return p.returncode == 0


# --- Main ---

async def main():
    DBG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[orch] v6 launch Chrome @ --start-maximized, viewport {FFMPEG_W}x{FFMPEG_H}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path=CHROMIUM_PATH,
            args=CHROME_ARGS,
        )
        ctx = await browser.new_context(
            viewport={"width": FFMPEG_W, "height": FFMPEG_H},
            locale="zh-CN",
            device_scale_factor=1,
        )
        page = await ctx.new_page()

        print("[orch] navigate to URL")
        await page.goto(URL, wait_until="domcontentloaded", timeout=10000)
        try:
            await page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        await page.wait_for_timeout(4000)
        await debug_shot(page, "v6-warmup-final")

        # 启 ffmpeg
        print("[orch] start ffmpeg")
        ffmpeg = start_ffmpeg()
        time.sleep(2)  # 等 ffmpeg 稳定
        print("[orch] ffmpeg started, begin demo")

        start = time.time()
        try:
            await section0_opening(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section1_s1(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section2_s2(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section3_s3(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section4_s4(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section5_s5(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section6_close(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
        except Exception as e:
            print(f"!! main flow error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"[orch] demo done in {time.time()-start:.1f}s")
            try:
                await ctx.close()
                await browser.close()
            except Exception:
                pass

    wait_ffmpeg(ffmpeg, timeout=240)
    if RECORDING.exists():
        size_mb = RECORDING.stat().st_size / 1024 / 1024
        print(f"[orch] v6 recording: {RECORDING} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
