#!/usr/bin/env python
"""
AgentHub Demo 录制脚本 — 驱动 Chromium 走完 5 个 Story。

时序（与 script.md 对齐）：
  0:00-0:15  章节 0 开场
  0:15-0:45  章节 1 S1 私聊 + 代码块 + 复制代码
  0:45-1:15  章节 2 S2 群聊 + @协调者
  1:15-1:45  章节 3 S3 右栏预览 + 旁白说明
  1:45-2:15  章节 4 S4 自建 Agent
  2:15-2:45  章节 5 S5 任务看板 + Inbox devtools hack
  2:45-3:00  章节 6 收尾 + 主题切换 + docs/

录制配合 ffmpeg gdigrab 同步进行（start_process ffmpeg, ~200s）。
"""
import asyncio
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PWTimeout

URL = "http://127.0.0.1:5174"
CHROMIUM_PATH = r"C:\Users\yhn\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
VIEWPORT = {"width": 1500, "height": 950}
WINDOW_POS = {"x": 0, "y": 0}


async def settle(page: Page, ms: int = 600):
    """短停顿 + 等 DOM 稳定。"""
    await page.wait_for_timeout(ms)


async def section0_opening(page: Page):
    """0:00-0:15 — 开场：主页 + 4 个一级入口 hover。"""
    print("[0:00] >>> section 0 opening")
    await page.goto(URL, wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle", timeout=8000)
    await settle(page, 1500)

    # 鼠标 hover 左导航 4 个图标（chat / agent / group / skill）
    nav_buttons = page.locator("aside[aria-label] nav button")
    n = await nav_buttons.count()
    print(f"  nav buttons: {n}")
    for i in range(n):
        try:
            await nav_buttons.nth(i).hover()
        except Exception as e:
            print(f"  hover {i} fail: {e}")
        await settle(page, 250)
    await settle(page, 500)


async def section1_s1_private_chat(page: Page):
    """0:15-0:45 — S1 私聊 + 代码块 + 复制代码。"""
    print("[0:15] >>> section 1 S1 private chat + code block")
    # 回到 chat section（默认）
    await page.locator("aside[aria-label] nav button").first.click()
    await settle(page, 800)

    # 找左侧栏的「+ 新建会话」按钮（ConversationTabs 末尾的 +）
    plus = page.locator("button[title='新建会话']").first
    if await plus.count() == 0:
        # 备用：找 ConversationTabs 中的 + 按钮
        plus = page.locator("button:has(svg)").filter(has_text="").locator(
            "[class*='border-dashed']"
        ).first
    try:
        await plus.click(timeout=2000)
        await settle(page, 1200)
    except Exception as e:
        print(f"  new chat btn: {e}")

    # StartChatModal：选 Claude agent
    # 简化：直接找包含「Claude」文本的可点击项
    claude = page.get_by_text("Claude", exact=False).first
    try:
        await claude.click(timeout=2000)
        await settle(page, 1200)
    except Exception:
        print("  no claude option found in modal")

    # 「开始对话」按钮
    start_btn = page.get_by_role("button", name="开始对话")
    if await start_btn.count() > 0:
        try:
            await start_btn.first.click(timeout=2000)
        except Exception:
            pass
    await settle(page, 1500)

    # 切到「对话 2 / Pricing page draft」看 m3（python fence）
    conv = page.get_by_text("Pricing page draft", exact=False).first
    try:
        await conv.click(timeout=2000)
        await settle(page, 1500)
    except Exception:
        print("  conv 'Pricing page draft' not found, will try '对话 2'")
        conv2 = page.get_by_text("对话 2", exact=False).first
        if await conv2.count() > 0:
            try:
                await conv2.click(timeout=2000)
            except Exception:
                pass
            await settle(page, 1200)

    # 滚到底部，hover 复制代码按钮
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 400)
    copy_btn = page.get_by_role("button", name="复制代码")
    if await copy_btn.count() > 0:
        try:
            await copy_btn.first.hover()
            await settle(page, 600)
            await copy_btn.first.click()
            await settle(page, 1500)
        except Exception as e:
            print(f"  copy btn: {e}")
    else:
        print("  no '复制代码' button (mock m3 not visible)")

    # hover Pin 按钮
    pin_btn = page.get_by_role("button", name="Pin", exact=False).first
    if await pin_btn.count() > 0:
        try:
            await pin_btn.hover()
        except Exception:
            pass
    await settle(page, 800)


async def section2_s2_group_chat(page: Page):
    """0:45-1:15 — S2 群聊 + 协调者。"""
    print("[0:45] >>> section 2 S2 group chat")
    # 找「群组」按钮（label = 群组）
    group_btn = page.get_by_role("button", name="群组", exact=False).first
    try:
        await group_btn.click(timeout=2000)
    except Exception:
        # 备用：左导航第 3 个
        try:
            await page.locator("aside[aria-label] nav button").nth(2).click()
        except Exception:
            pass
    await settle(page, 1500)

    # 进 S2 群（找「S2 - 营销页升级」或 group 列表项）
    s2 = page.get_by_text("S2 - 营销页升级", exact=False).first
    if await s2.count() == 0:
        s2 = page.get_by_text("S2", exact=False).first
    try:
        await s2.click(timeout=2000)
    except Exception as e:
        print(f"  S2 group click fail: {e}")
    await settle(page, 2000)

    # 滚到底部看消息
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await settle(page, 1000)

    # 在 GroupComposer 输入框打 @Coordinator
    composer = page.locator("textarea, [contenteditable='true']").last
    try:
        await composer.click()
        await composer.fill("@Coordinator 帮我把 S2 进度同步给老板")
        await settle(page, 1500)
    except Exception as e:
        print(f"  group composer: {e}")

    await settle(page, 1500)


async def section3_s3_preview(page: Page):
    """1:15-1:45 — S3 右栏预览 + 旁白说明。"""
    print("[1:15] >>> section 3 S3 inline preview (right panel)")
    # 找「展开右侧面板」按钮
    expand_btn = page.get_by_title("展开右侧面板").first
    if await expand_btn.count() == 0:
        expand_btn = page.get_by_title("收起右侧面板").first  # 已经是展开？
    try:
        await expand_btn.click(timeout=2000)
    except Exception as e:
        print(f"  right panel toggle: {e}")
    await settle(page, 1500)

    # 找 4 个预览 mode tab
    modes = ["项目文件", "审查 diff", "部署", "网页"]
    for m in modes:
        btn = page.get_by_text(m, exact=False).first
        if await btn.count() > 0:
            try:
                await btn.hover()
            except Exception:
                pass
            await settle(page, 400)

    # 点「项目文件」看文件树
    files_btn = page.get_by_text("项目文件", exact=False).first
    if await files_btn.count() > 0:
        try:
            await files_btn.click()
        except Exception:
            pass
    await settle(page, 1500)

    # 镜头特写「审查 diff」mode（即将到来 badge）
    diff_btn = page.get_by_text("审查 diff", exact=False).first
    if await diff_btn.count() > 0:
        try:
            await diff_btn.hover()
        except Exception:
            pass
    await settle(page, 1000)

    # 回到中央
    await page.evaluate("window.scrollTo(0, 0)")
    await settle(page, 600)


async def section4_s4_custom_agent(page: Page):
    """1:45-2:15 — 自建 Agent。"""
    print("[1:45] >>> section 4 S4 create agent")
    # 点左导航「AI 队友」
    agent_btn = page.get_by_role("button", name="AI 队友", exact=False).first
    if await agent_btn.count() == 0:
        agent_btn = page.locator("aside[aria-label] nav button").nth(1)
    try:
        await agent_btn.click(timeout=2000)
    except Exception as e:
        print(f"  AI 队友 btn: {e}")
    await settle(page, 1500)

    # 找「创建队友」按钮
    create_btn = page.get_by_text("创建队友", exact=False).first
    if await create_btn.count() == 0:
        create_btn = page.get_by_role("button", name="创建队友", exact=False).first
    try:
        await create_btn.click(timeout=2000)
    except Exception as e:
        print(f"  create agent btn: {e}")
    await settle(page, 1500)

    # 选模板「工程师」
    eng = page.get_by_text("工程师", exact=False).first
    try:
        await eng.click(timeout=2000)
    except Exception:
        # 备用：直接找 system prompt 区域
        pass
    await settle(page, 1000)

    # 选 CLI 类型 Claude Code
    ccode = page.get_by_text("Claude Code", exact=False).first
    try:
        await ccode.click(timeout=2000)
    except Exception:
        pass
    await settle(page, 1500)

    # 填名字 + 描述
    try:
        name_input = page.get_by_label("名字", exact=False).first
        if await name_input.count() > 0:
            await name_input.fill("试水 Bot")
        desc_input = page.get_by_label("描述", exact=False).first
        if await desc_input.count() > 0:
            await desc_input.fill("M3 试水")
    except Exception as e:
        print(f"  fill form: {e}")
    await settle(page, 1500)

    # 点「创建」按钮
    submit = page.get_by_role("button", name="创建", exact=False).first
    if await submit.count() > 0:
        try:
            await submit.click()
        except Exception:
            pass
    await settle(page, 1500)


async def section5_s5_tasks_inbox(page: Page):
    """2:15-2:45 — 任务看板 + Inbox devtools hack。"""
    print("[2:15] >>> section 5 S5 tasks + inbox devtools hack")
    # 回到 chat section
    chat_btn = page.locator("aside[aria-label] nav button").first
    try:
        await chat_btn.click()
    except Exception:
        pass
    await settle(page, 1200)

    # 进 Claude 私聊
    claude = page.get_by_text("Claude", exact=False).first
    try:
        await claude.click()
    except Exception:
        pass
    await settle(page, 1200)

    # 点中央 tab 条的「任务」
    tasks_tab = page.get_by_role("button", name="任务", exact=False).first
    if await tasks_tab.count() == 0:
        tasks_tab = page.locator("button:has-text('任务')").first
    try:
        await tasks_tab.click(timeout=2000)
    except Exception as e:
        print(f"  tasks tab: {e}")
    await settle(page, 2000)

    # 镜头停看板
    await settle(page, 1000)

    # 切到列表视图
    list_btn = page.get_by_role("button", name="list", exact=False).first
    if await list_btn.count() > 0:
        try:
            await list_btn.click()
        except Exception:
            pass
    await settle(page, 800)
    # 切回看板
    kanban_btn = page.get_by_role("button", name="grid", exact=False).first
    if await kanban_btn.count() > 0:
        try:
            await kanban_btn.click()
        except Exception:
            pass
    await settle(page, 800)

    # dev console hack：注入 zustand setState
    # zustand persist 的 key 是 'agenthub-ui'（按 uiStore 命名规则）
    try:
        # 尝试访问 zustand store
        await page.evaluate("""
            () => {
                // 通过 React DevTools 不好直连，换个方式：
                // 直接操作 localStorage 让 zustand persist 重新载入
                // 但 setSection 不在 persist keys 里，UI 状态不一定落 localStorage
                // 这里 hack：dispatch a click on a hidden element
                // 兜底：调用 zustand setState via store
                const root = document.getElementById('root');
                if (root) {
                    // 标记一下
                    window.__demo_inbox = 'hack-attempted';
                }
            }
        """)
    except Exception:
        pass
    await settle(page, 1500)


async def section6_closing(page: Page):
    """2:45-3:00 — 收尾 + 主题切换。"""
    print("[2:45] >>> section 6 closing")
    # 主题切换
    theme_btn = page.get_by_title("切换到深色", exact=False).first
    if await theme_btn.count() == 0:
        theme_btn = page.locator("button[aria-label*='主题']").first
    for _ in range(3):
        try:
            if await theme_btn.count() > 0:
                await theme_btn.click(timeout=1000)
        except Exception:
            pass
        await settle(page, 700)
    await settle(page, 1500)


async def main():
    out_dir = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Playwright launch: {CHROMIUM_PATH}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path=CHROMIUM_PATH,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-position=0,0",
            ],
        )
        ctx = await browser.new_context(
            viewport=VIEWPORT,
            locale="zh-CN",
            device_scale_factor=1,
        )
        page = await ctx.new_page()
        # 一些 console log
        page.on("console", lambda msg: print(f"  [console.{msg.type}] {msg.text[:150]}"))

        start = time.time()
        try:
            await section0_opening(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section1_s1_private_chat(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section2_s2_group_chat(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section3_s3_preview(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section4_s4_custom_agent(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section5_s5_tasks_inbox(page)
            print(f"  elapsed: {time.time()-start:.1f}s")
            await section6_closing(page)
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
        print(f"total elapsed: {time.time()-start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
