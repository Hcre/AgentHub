import subprocess, json, sys

code_js = """async (page) => {
  // Refresh and navigate to S2 group chat
  await page.goto('http://127.0.0.1:5174/');
  await page.waitForTimeout(3000);

  // Click 群组 nav (left sidebar) - 3 buttons have text 群组, use title= attr
  const groupsNav = page.locator('button[title="群组"]').first();
  await groupsNav.click();
  await page.waitForTimeout(1500);

  // G2: Now click the S2 group card (整卡点击 - new UX)
  // Find article with S2 text
  const s2Card = page.locator('article:has-text("S2")').first();
  if ((await s2Card.count()) === 0) return { error: 'S2 card not found' };
  const cardBox = await s2Card.boundingBox();
  const beforeUrl = page.url();
  await s2Card.click();
  await page.waitForTimeout(2000);
  const afterUrl = page.url();
  const afterH1 = await page.evaluate(() => document.querySelector('h1')?.innerText);

  // Now we're in S2 group chat. Find Claude S2 message
  const claudeMsg = page.locator('p:has-text("Hero")').first();
  await claudeMsg.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  // G1: hover group/msg to reveal Pin button (group/msg uses group-hover:opacity-100)
  const groupMsg = claudeMsg.locator('xpath=ancestor::div[contains(@class, "group/msg")][1]');
  const groupMsgBox = await groupMsg.boundingBox();
  if (!groupMsgBox) return { error: 'no group/msg box' };

  // Hover the group/msg
  await groupMsg.hover();
  await page.waitForTimeout(800);

  // Check for Pin button
  const pinBtn = groupMsg.locator('[data-testid="group-pin-btn"]');
  const pinCount = await pinBtn.count();
  const pinVisible = pinCount > 0 ? await pinBtn.first().isVisible() : false;
  const pinAriaLabel = pinCount > 0 ? await pinBtn.first().getAttribute('aria-label') : null;
  const pinDataPinned = pinCount > 0 ? await pinBtn.first().getAttribute('data-pinned') : null;

  // Check for copy code button (OpenCode message has PricingCard code)
  const opencodeMsg = page.locator('p:has-text("PricingCard")').first();
  let copyBtnCount = 0;
  let copyBtnVisible = false;
  if ((await opencodeMsg.count()) > 0) {
    const ocMsg = opencodeMsg.locator('xpath=ancestor::div[contains(@class, "group/msg")][1]');
    if ((await ocMsg.count()) > 0) {
      await ocMsg.hover();
      await page.waitForTimeout(500);
      const copyBtn = ocMsg.locator('[data-testid="group-copy-code-btn"]');
      copyBtnCount = await copyBtn.count();
      copyBtnVisible = copyBtnCount > 0 ? await copyBtn.first().isVisible() : false;
    }
  }

  return {
    g2_urlBefore: beforeUrl,
    g2_urlAfter: afterUrl,
    g2_h1: afterH1,
    g2_cardBox: cardBox ? { x: cardBox.x, y: cardBox.y, w: cardBox.width, h: cardBox.height } : null,
    g1_pinCount: pinCount,
    g1_pinVisible: pinVisible,
    g1_pinAriaLabel: pinAriaLabel,
    g1_pinDataPinned: pinDataPinned,
    g1_copyBtnCount: copyBtnCount,
    g1_copyBtnVisible: copyBtnVisible,
  };
}"""

args = {"code": code_js}
result = subprocess.run(
    [r"C:\Users\yhn\.mavis\bin\mavis.cmd", "mcp", "call", "playwright", "browser_run_code", "--stdin"],
    input=json.dumps(args, ensure_ascii=False),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("STDOUT:", result.stdout[:3500])
print("STDERR:", result.stderr[:300])
