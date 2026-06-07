#!/usr/bin/env python
"""
AgentHub Demo v5 — 强制 Chrome 窗口位置到 DISPLAY1 (1707x1067, 0,0) + 录全屏。

策略：
  1. 启动 Chromium headless=False
  2. 用 Win32 SetWindowPos 把窗口强制移到 (0, 0) on DISPLAY1
  3. ffmpeg gdigrab 录 (0, 0) to (1707, 1067) — 全 DISPLAY1
  4. 走 5 个 story
  5. 等 ffmpeg 完成
"""
import asyncio
import ctypes
import ctypes.wintypes
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page

URL = "http://127.0.0.1:5174"
CHROMIUM_PATH = r"C:\Users\yhn\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
WINDOW_X = 0  # DISPLAY1 left
WINDOW_Y = 0
WINDOW_W = 1707  # DISPLAY1 width
WINDOW_H = 1067  # DISPLAY1 height
VIDEO_DIR = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video")
DBG_DIR = VIDEO_DIR / "_dbg"
RECORDING = VIDEO_DIR / "raw-recording.mp4"
FFMPEG_DURATION = 200


# --- Win32 SetWindowPos to force position ---
user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
SetWindowPos = user32.SetWindowPos


def force_chrome_to_monitor():
    """Find any Chrome window with 'AgentHub' or 'localhost' in title, move to (0,0)."""
    found = []

    def callback(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value
        if "AgentHub" in title or "127.0.0.1" in title or "Chrome" in title or "localhost" in title:
            found.append((hwnd, title))
        return True

    EnumWindows(EnumWindowsProc(callback), 0)
    print(f"[win32] found {len(found)} chrome-like windows")
    for hwnd, title in found:
        # SWP_NOZORDER=4, SWP_SHOWWINDOW=64, SWP_NOACTIVATE=16
        SetWindowPos(hwnd, 0, WINDOW_X, WINDOW_Y, WINDOW_W, WINDOW_H, 0x0040 | 0x0010)
        print(f"  moved hwnd={hwnd} '{title[:40]}' -> ({WINDOW_X},{WINDOW_Y}) {WINDOW_W}x{WINDOW_H}")


# --- Playwright helpers ---

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
        await page.screenshot(path=str(DBG_DIR / f"dbg-{label}.png"), full_page=False)
    except Exception:
        pass


# --- 5 stories (with more robust selectors) ---

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
    # 默认 chat 状态。点「对话 2」tab 切到 m3
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

    # 模板 click — 用 button:has-text 精确定位到 modal 内的 button
    try:
        # 工程师是第 2 个模板（在 modal 内）
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

    # 选 CLI Claude Code（modal 下一步后）
    try:
        # 模板点完后会自动到 step 2，CLI 选项出现在那里
        await click_text(page, "Claude Code", timeout_ms=2500)
    except Exception as e:
        print(f"  claude code: {e}")
    await settle(page, 1500)
    await debug_shot(page, "04-cli")

    # 填名字
    try:
        for label in ["名字", "名称"]:
            loc = page.get_by_label(label, exact=False).first
            if await loc.count() > 0:
                await loc.fill("试水 Bot")
                break
    except Exception:
        pass
    await settle(page, 800)

    # 点创建
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


# --- orchestration ---

def start_ffmpeg():
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    if RECORDING.exists():
        RECORDING.unlink()
    args = [
        "ffmpeg.exe", "-y",
        "-f", "gdigrab",
        "-framerate", "30",
        "-offset_x", str(WINDOW_X),
        "-offset_y", str(WINDOW_Y),
        "-video_size", f"{WINDOW_W}x{WINDOW_H}",
        "-i", "desktop",
        "-t", str(FFMPEG_DURATION),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-loglevel", "error",
        str(RECORDING),
    ]
    print(f"[orch] ffmpeg: {' '.join(args)}")
    p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    return p


def wait_ffmpeg(p, timeout=240):
    print(f"[orch] wait ffmpeg (PID={p.pid})...")
    start = time.time()
    while p.poll() is None:
        time.sleep(2)
        if int(time.time() - start) % 30 == 0:
            print(f"  ... {int(time.time()-start)}s")
        if time.time() - start > timeout:
            print("[orch] ffmpeg timeout, kill")
            p.kill()
            return False
    print(f"[orch] ffmpeg done, rc={p.returncode}")
    return p.returncode == 0


async def main():
    DBG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[orch] launch Chrome @ ({WINDOW_X},{WINDOW_Y}) {WINDOW_W}x{WINDOW_H}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path=CHROMIUM_PATH,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                f"--window-position={WINDOW_X},{WINDOW_Y}",
                f"--window-size={WINDOW_W},{WINDOW_H}",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": WINDOW_W, "height": WINDOW_H},
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
        await debug_shot(page, "warmup-final")

        # 强制把窗口移到 DISPLAY1 (0,0,1707,1067)
        print("[orch] force window position via Win32 SetWindowPos")
        force_chrome_to_monitor()
        await page.wait_for_timeout(2000)
        await debug_shot(page, "after-force-move")

        # 启动 ffmpeg
        ffmpeg = start_ffmpeg()
        time.sleep(2)
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
        print(f"[orch] recording: {RECORDING} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
