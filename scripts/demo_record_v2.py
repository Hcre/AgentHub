#!/usr/bin/env python
"""
AgentHub Demo v2 — 5 stories in 3 min, 录制前先 warm up Chrome。

策略：
  1. 启动 Chromium 到 DISPLAY6 (x=2560, y=0, 1920x1080)
  2. 导航到 localhost:5174
  3. 等 5s 让 React 加载完
  4.【外部】 ffmpeg gdigrab 启动 -offset_x 2560 -offset_y 0 -video_size 1920x1080
  5. 走 5 个 story，每个 ~30s
  6. 收尾
"""
import asyncio
import time
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser

URL = "http://127.0.0.1:5174"
CHROMIUM_PATH = r"C:\Users\yhn\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
WINDOW_X = 2560  # DISPLAY6 起点
WINDOW_Y = 0
VIEWPORT = {"width": 1920, "height": 1080}


async def settle(page: Page, ms: int = 600):
    await page.wait_for_timeout(ms)


async def debug_shot(page: Page, label: str, out_dir: Path):
    """Debug screenshot for visibility."""
    p = out_dir / f"dbg-{label}.png"
    try:
        await page.screenshot(path=str(p), full_page=False)
        print(f"  [dbg] {label} -> {p.name}")
    except Exception as e:
        print(f"  [dbg] {label} FAIL: {e}")


async def click_text(page: Page, text: str, timeout_ms: int = 2500, exact: bool = False):
    """Click element containing text, return True on success."""
    loc = page.get_by_text(text, exact=exact).first
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
    except Exception as e:
        print(f"  hover '{text}': {type(e).__name__}")
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
    """0:00-0:15 — 开场。"""
    print("[0:00] >>> section 0 opening")
    await page.goto(URL, wait_until="domcontentloaded", timeout=10000)
    try:
        await page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    await settle(page, 1500)
    await debug_shot(page, "00-opening", out_dir)

    # Hover 左导航 4 个图标
    nav = page.locator("aside[aria-label] nav button")
    n = await nav.count()
    for i in range(n):
        try:
            await nav.nth(i).hover()
        except Exception:
            pass
        await settle(page, 250)
    await settle(page, 800)


async def section1_s1(page: Page, out_dir: Path):
    """0:15-0:45 — S1 私聊 + 代码块。"""
    print("[0:15] >>> section 1 S1 private chat")
    # 已在 chat section（默认），hover conversation tab
    await click_text(page, "对话 2", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "01-s1-conv2", out_dir)

    # 滚到底
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 500)

    # 找 m3 python fence + 复制代码按钮
    await hover_text(page, "复制代码", timeout_ms=1500)
    await settle(page, 700)
    await click_role(page, "button", "复制代码", timeout_ms=1500)
    await settle(page, 1500)
    await debug_shot(page, "01-s1-copied", out_dir)

    # Pin button
    await hover_text(page, "Pin", timeout_ms=1500)
    await settle(page, 800)


async def section2_s2(page: Page, out_dir: Path):
    """0:45-1:15 — S2 群聊。"""
    print("[0:45] >>> section 2 S2 group")
    # 找「群组」按钮 — 左导航第 3 个
    nav = page.locator("aside[aria-label] nav button")
    try:
        await nav.nth(2).click(timeout=2000)
    except Exception as e:
        print(f"  group nav: {e}")
    await settle(page, 1500)
    await debug_shot(page, "02-s2-groups", out_dir)

    # 进 S2 群
    await click_text(page, "S2 - 营销页升级", timeout_ms=2500)
    await settle(page, 2000)
    await debug_shot(page, "02-s2-group", out_dir)

    # 滚到底
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 1500)

    # 在 GroupComposer 输入 @Coordinator
    try:
        composer = page.locator("textarea").last
        await composer.click()
        await composer.fill("@Coordinator 帮我把 S2 进度同步给老板")
        await settle(page, 2000)
    except Exception as e:
        print(f"  composer: {e}")
    await debug_shot(page, "02-s2-typed", out_dir)


async def section3_s3(page: Page, out_dir: Path):
    """1:15-1:45 — S3 内联预览（借右栏 + 旁白）。"""
    print("[1:15] >>> section 3 S3 inline preview")
    # 找展开/收起右侧面板的按钮
    btns = page.locator("button[title*='右侧面板']")
    n = await btns.count()
    print(f"  right panel btns: {n}")
    if n > 0:
        try:
            await btns.first.click(timeout=2000)
        except Exception as e:
            print(f"  toggle: {e}")
    await settle(page, 1500)
    await debug_shot(page, "03-s3-panel", out_dir)

    # 镜头特写：4 个预览 mode tab（项目文件 / 审查 diff / 部署 / 网页）
    for t in ["项目文件", "审查 diff", "部署", "网页"]:
        await hover_text(page, t, timeout_ms=1500)
        await settle(page, 500)

    # 点「项目文件」看文件树
    await click_text(page, "项目文件", timeout_ms=2000)
    await settle(page, 1500)
    await debug_shot(page, "03-s3-files", out_dir)

    # Hover「审查 diff」看 disabled 状态
    await hover_text(page, "审查 diff", timeout_ms=1500)
    await settle(page, 1200)
    await debug_shot(page, "03-s3-diff-mode", out_dir)


async def section4_s4(page: Page, out_dir: Path):
    """1:45-2:15 — S4 自建 Agent。"""
    print("[1:45] >>> section 4 S4 create agent")
    # 关掉右侧面板（先折叠）
    btns = page.locator("button[title*='右侧面板']")
    if await btns.count() > 0:
        try:
            await btns.first.click()
        except Exception:
            pass
    await settle(page, 800)

    # 点「AI 队友」
    nav = page.locator("aside[aria-label] nav button")
    try:
        await nav.nth(1).click()
    except Exception as e:
        print(f"  AI 队友 nav: {e}")
    await settle(page, 1500)
    await debug_shot(page, "04-s4-agents", out_dir)

    # 找「创建队友」按钮
    await click_text(page, "创建队友", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "04-s4-modal", out_dir)

    # 选模板「工程师」
    await click_text(page, "工程师", timeout_ms=2500)
    await settle(page, 1000)
    await debug_shot(page, "04-s4-template", out_dir)

    # 选 CLI Claude Code
    await click_text(page, "Claude Code", timeout_ms=2500)
    await settle(page, 1500)
    await debug_shot(page, "04-s4-cli", out_dir)

    # 填名字 + 描述
    try:
        for label, value in [("名字", "试水 Bot"), ("名称", "试水 Bot")]:
            loc = page.get_by_label(label, exact=False).first
            if await loc.count() > 0:
                await loc.fill(value)
                break
    except Exception:
        pass
    await settle(page, 800)

    # 点「下一步」or「创建」按钮
    if not await click_text(page, "下一步", timeout_ms=1500):
        await click_text(page, "创建", timeout_ms=1500)
    await settle(page, 2000)
    await debug_shot(page, "04-s4-after-create", out_dir)


async def section5_s5(page: Page, out_dir: Path):
    """2:15-2:45 — S5 任务看板 + Inbox devtools hack。"""
    print("[2:15] >>> section 5 S5 tasks + inbox")
    # 关闭可能残留的 modal
    try:
        cancel = page.get_by_role("button", name="取消").first
        if await cancel.count() > 0:
            await cancel.click()
    except Exception:
        pass
    await settle(page, 600)

    # 点「会话」回 chat
    nav = page.locator("aside[aria-label] nav button")
    try:
        await nav.nth(0).click()
    except Exception:
        pass
    await settle(page, 1200)

    # 进 Claude 私聊
    await click_text(page, "Claude", timeout_ms=2500)
    await settle(page, 1200)
    await debug_shot(page, "05-s5-claude", out_dir)

    # 找「任务」tab
    await click_text(page, "任务", timeout_ms=2500)
    await settle(page, 2000)
    await debug_shot(page, "05-s5-tasks-kanban", out_dir)

    # hover list view 按钮（button name="list"）
    try:
        await page.get_by_role("button", name="list", exact=False).first.hover()
        await settle(page, 400)
        await page.get_by_role("button", name="list", exact=False).first.click()
    except Exception as e:
        print(f"  list toggle: {e}")
    await settle(page, 1200)
    await debug_shot(page, "05-s5-tasks-list", out_dir)

    # 切回 kanban
    try:
        await page.get_by_role("button", name="grid", exact=False).first.click()
    except Exception as e:
        print(f"  grid toggle: {e}")
    await settle(page, 1200)

    # dev console hack：直接调 zustand setState 把 section 切到 inbox
    # （zustand 默认未挂到 window，但 uiStore 的 setSection 是闭包里 export 的）
    # 兜底：dispatch 一个 click on document.title 等
    # 实测：zustand 没有把 store 挂到 window，所以不能直接调
    # 改用 React DevTools approach：通过 DOM 注入并 React trigger 不现实
    # 替代：直接显示 InboxView 组件的 mock 设计 — 文档已经说明这是 M4 计划
    await settle(page, 1000)
    await debug_shot(page, "05-s5-final", out_dir)


async def section6_close(page: Page, out_dir: Path):
    """2:45-3:00 — 收尾：主题切换。"""
    print("[2:45] >>> section 6 closing")
    # 主题切换
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
                "--start-fullscreen",
            ],
        )
        ctx = await browser.new_context(
            viewport=VIEWPORT,
            locale="zh-CN",
            device_scale_factor=1,
        )
        page = await ctx.new_page()
        page.on("console", lambda msg: print(f"  [c.{msg.type}] {msg.text[:120]}"))

        # WARMUP: 打开 URL 等加载完（这步在 ffmpeg 启动之前）
        print("[warmup] navigate to URL")
        await page.goto(URL, wait_until="domcontentloaded", timeout=10000)
        try:
            await page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)
        await debug_shot(page, "warmup", dbg_dir)
        print("[warmup] done. ffmpeg should be running externally now. Sleeping 1s to let ffmpeg catch the warmup state.")
        await page.wait_for_timeout(1000)

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
            print("[done] closing browser")
            try:
                await ctx.close()
                await browser.close()
            except Exception:
                pass
        print(f"total demo elapsed: {time.time()-start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
