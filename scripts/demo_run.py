#!/usr/bin/env python
"""
AgentHub Demo 录制 v3 — 第二阶段：连接已打开的 Chrome 走 5 个 story。

前置：demo_warmup.py 已经在 DISPLAY6 打开 Chrome。
"""
import asyncio
import time
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

URL = "http://127.0.0.1:5174"
CHROMIUM_PATH = r"C:\Users\yhn\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
# 通过 CDP 连接到已有 Chrome
CDP_URL = "http://127.0.0.1:9222"  # 默认 Playwright debug port
VIEWPORT = {"width": 1920, "height": 1080}


async def settle(page: Page, ms: int = 600):
    await page.wait_for_timeout(ms)


async def debug_shot(page: Page, label: str, out_dir: Path):
    p = out_dir / f"dbg-{label}.png"
    try:
        await page.screenshot(path=str(p), full_page=False)
        print(f"  [dbg] {label} -> {p.name}")
    except Exception as e:
        print(f"  [dbg] {label} FAIL: {e}")


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
        print(f"  click '{text}': {type(e).__name__}")
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


async def section0_opening(page: Page, out_dir: Path):
    print("[0:00] >>> section 0 opening")
    # 已在主页，hover 4 nav icons
    nav = page.locator("aside[aria-label] nav button")
    n = await nav.count()
    for i in range(n):
        try:
            await nav.nth(i).hover()
        except Exception:
            pass
        await settle(page, 300)
    await settle(page, 1200)
    await debug_shot(page, "00-opening", out_dir)


async def section1_s1(page: Page, out_dir: Path):
    print("[0:15] >>> section 1 S1")
    await click_text(page, "对话 2", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "01-s1-conv", out_dir)

    # 滚到底
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 500)

    await hover_text(page, "复制代码", timeout_ms=1500)
    await settle(page, 700)
    await click_role(page, "button", "复制代码", timeout_ms=1500)
    await settle(page, 1500)
    await debug_shot(page, "01-s1-copied", out_dir)

    await hover_text(page, "Pin", timeout_ms=1500)
    await settle(page, 800)


async def section2_s2(page: Page, out_dir: Path):
    print("[0:45] >>> section 2 S2 group")
    nav = page.locator("aside[aria-label] nav button")
    try:
        await nav.nth(2).click(timeout=2500)
    except Exception as e:
        print(f"  group nav: {e}")
    await settle(page, 1500)
    await debug_shot(page, "02-s2-groups", out_dir)

    await click_text(page, "S2 - 营销页升级", timeout_ms=2500)
    await settle(page, 2000)
    await debug_shot(page, "02-s2-group", out_dir)

    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 1500)

    try:
        composer = page.locator("textarea").last
        await composer.click()
        await composer.fill("@Coordinator 帮我把 S2 进度同步给老板")
        await settle(page, 2000)
    except Exception as e:
        print(f"  composer: {e}")
    await debug_shot(page, "02-s2-typed", out_dir)


async def section3_s3(page: Page, out_dir: Path):
    print("[1:15] >>> section 3 S3 inline preview")
    btns = page.locator("button[title*='右侧面板']")
    if await btns.count() > 0:
        try:
            await btns.first.click(timeout=2500)
        except Exception as e:
            print(f"  toggle: {e}")
    await settle(page, 1500)
    await debug_shot(page, "03-s3-panel", out_dir)

    for t in ["项目文件", "审查 diff", "部署", "网页"]:
        await hover_text(page, t, timeout_ms=1500)
        await settle(page, 500)

    await click_text(page, "项目文件", timeout_ms=2000)
    await settle(page, 1500)
    await debug_shot(page, "03-s3-files", out_dir)

    await hover_text(page, "审查 diff", timeout_ms=1500)
    await settle(page, 1200)
    await debug_shot(page, "03-s3-diff-mode", out_dir)


async def section4_s4(page: Page, out_dir: Path):
    print("[1:45] >>> section 4 S4 create agent")
    # 关掉右栏
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
    await debug_shot(page, "04-s4-agents", out_dir)

    await click_text(page, "创建队友", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "04-s4-modal", out_dir)

    await click_text(page, "工程师", timeout_ms=2500)
    await settle(page, 1000)
    await debug_shot(page, "04-s4-template", out_dir)

    await click_text(page, "Claude Code", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "04-s4-cli", out_dir)

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

    if not await click_text(page, "下一步", timeout_ms=1500):
        if not await click_text(page, "创建", timeout_ms=1500):
            print("  no submit button found, modal may still be open")
    await settle(page, 2000)
    await debug_shot(page, "04-s4-after-create", out_dir)


async def section5_s5(page: Page, out_dir: Path):
    print("[2:15] >>> section 5 S5 tasks + inbox")
    # 关 modal
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
    await debug_shot(page, "05-s5-claude", out_dir)

    await click_text(page, "任务", timeout_ms=2500)
    await settle(page, 2000)
    await debug_shot(page, "05-s5-kanban", out_dir)

    try:
        await page.get_by_role("button", name="list", exact=False).first.hover()
        await settle(page, 400)
        await page.get_by_role("button", name="list", exact=False).first.click()
    except Exception as e:
        print(f"  list: {e}")
    await settle(page, 1200)
    await debug_shot(page, "05-s5-list", out_dir)

    try:
        await page.get_by_role("button", name="grid", exact=False).first.click()
    except Exception as e:
        print(f"  grid: {e}")
    await settle(page, 1200)
    await debug_shot(page, "05-s5-final", out_dir)


async def section6_close(page: Page, out_dir: Path):
    print("[2:45] >>> section 6 closing")
    theme = page.locator("button[aria-label*='主题']").first
    for _ in range(3):
        try:
            if await theme.count() > 0:
                await theme.click()
        except Exception:
            pass
        await settle(page, 600)
    await settle(page, 1500)
    await debug_shot(page, "06-close", out_dir)


async def main():
    out_dir = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video")
    out_dir.mkdir(parents=True, exist_ok=True)
    dbg_dir = out_dir / "_dbg"
    dbg_dir.mkdir(parents=True, exist_ok=True)

    print(f"[demo] connecting to existing Chrome @ {CDP_URL}")
    async with async_playwright() as p:
        # 连接已打开的 Chrome
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"!! CDP connect fail: {e}")
            print("   fallback: launch new chrome")
            browser = await p.chromium.launch(
                headless=False,
                executable_path=CHROMIUM_PATH,
                args=[
                    "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                    f"--window-position=2560,0",
                    f"--window-size=1920,1080",
                    "--remote-debugging-port=9222",
                ],
            )

        # 取所有 contexts
        contexts = browser.contexts
        if not contexts:
            ctx = await browser.new_context(viewport=VIEWPORT, locale="zh-CN")
        else:
            ctx = contexts[0]
        # 取 page
        pages = ctx.pages
        if not pages:
            page = await ctx.new_page()
        else:
            page = pages[0]
        await page.bring_to_front()
        # 跳转主页
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=8000)
        except Exception:
            pass
        await settle(page, 2000)
        await debug_shot(page, "demo-start", dbg_dir)

        start = time.time()
        try:
            await section0_opening(page, dbg_dir)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section1_s1(page, dbg_dir)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section2_s2(page, dbg_dir)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section3_s3(page, dbg_dir)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section4_s4(page, dbg_dir)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section5_s5(page, dbg_dir)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section6_close(page, dbg_dir)
            print(f"  elapsed: {time.time()-start:.1f}s")
        except Exception as e:
            print(f"!! main flow error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 不关 context/browser，留给 warmup 控制
            print("[demo] done (browser left running)")
        print(f"total demo elapsed: {time.time()-start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
