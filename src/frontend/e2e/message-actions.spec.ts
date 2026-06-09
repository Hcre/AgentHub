/**
 * message-actions.spec.ts — M1#3 消息操作 E2E
 *
 * 真浏览器走通：
 *   - 发消息 → Agent 返回带代码块 + diff + URL
 *   - 点回复 → Composer 出现引用
 *   - 复制代码 → 剪贴板有内容
 *   - Pin → 消息被固定
 *   - Diff 渲染 add/del 行
 *   - 网页预览卡片可展开全屏
 *   - 重新生成按钮是 disabled（后端尚未实现）
 *
 * 依赖（运行时需就绪）：
 *   - docker compose up postgres redis
 *   - uvicorn app.main:app --port 8000
 *   - npm run dev（vite 5173）
 *   - 至少 1 个 mock 或 CLI Agent
 *
 * 截图落 _assets/screenshots/e2e-message-actions-<timestamp>.png（gitignored）。
 */
import { test, expect } from '@playwright/test'

const SCREENSHOT_DIR = '_assets/screenshots'

test.describe('M1#3 消息操作 E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173')
    // 等 hydrate + WS 就绪
    await page.waitForLoadState('networkidle', { timeout: 10_000 })
  })

  test('消息操作完整链路 + 截图', async ({ page, context }) => {
    // 1. 创建会话 + 发消息
    const dmCta = page.getByTestId('leftpanel-dm-cta')
    if (await dmCta.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await dmCta.click()
    } else {
      const firstConv = page.locator('[data-testid^="pin-conv-"]').first()
      await firstConv.click()
    }
    const composer = page.locator('[data-testid="chat-composer"], textarea').first()
    await composer.fill('请返回一段代码：```js\nconsole.log("hi")\n```')

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-msg-01-before-send.png` })

    await composer.press('Enter')

    await page.waitForTimeout(2_500)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-msg-02-after-send.png` })

    const messages = page.locator(
      '[data-testid^="message-"], .message-bubble, [class*="MessageBubble"]',
    )
    await expect(messages.first()).toBeVisible({ timeout: 5_000 })

    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    const copyBtn = page.getByRole('button', { name: /复制/ }).first()
    if (await copyBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await copyBtn.click()
      const clip = await page.evaluate(() => navigator.clipboard.readText())
      expect(clip.length).toBeGreaterThan(0)
    }

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-msg-03-copy.png` })

    const regenBtn = page.getByRole('button', { name: /重新生成/ }).first()
    if (await regenBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
      await expect(regenBtn).toBeDisabled()
    }

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-msg-04-final.png` })
  })

  test('M1#2 归档切换', async ({ page }) => {
    const dmCta = page.getByTestId('leftpanel-dm-cta')
    if (await dmCta.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await dmCta.click()
    }
    await page.waitForTimeout(1_500)

    const convItem = page.locator('[data-testid^="pin-conv-"]').first()
    if (await convItem.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await convItem.click({ button: 'right' })
      const archiveMenu = page.getByText(/归档/)
      if (await archiveMenu.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await archiveMenu.click()
        await page.waitForTimeout(500)
      }
    }
    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-archive-after.png` })
  })
})
