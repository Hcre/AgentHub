import subprocess, json, sys

code_js = """async (page) => {
  // Find Claude S2 message
  const claudeMsg = page.locator('p:has-text("Hero")').first();
  await claudeMsg.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Find message container
  const msg = claudeMsg.locator('xpath=ancestor::div[2]');
  const cnt = await msg.count();
  if (cnt === 0) return { error: 'no message found' };

  // BEFORE hover
  const before = await page.evaluate(() => Array.from(document.querySelectorAll('button')).length);
  const beforeBtns = await page.evaluate(() => Array.from(document.querySelectorAll('button')).map(b => (b.title || b.getAttribute('aria-label') || b.innerText || '').substring(0, 40)).filter(t => t));

  // Use playwright .hover() API
  await msg.hover();
  await page.waitForTimeout(1000);

  // AFTER hover
  const after = await page.evaluate(() => Array.from(document.querySelectorAll('button')).length);
  const afterBtns = await page.evaluate(() => Array.from(document.querySelectorAll('button')).map(b => (b.title || b.getAttribute('aria-label') || b.innerText || '').substring(0, 40)).filter(t => t));

  const newBtns = afterBtns.filter(b => !beforeBtns.includes(b));
  return { before, after, newBtns, msgBox: await msg.boundingBox() };
}"""

args = {"code": code_js}
result = subprocess.run(
    [r"C:\Users\yhn\.mavis\bin\mavis.cmd", "mcp", "call", "playwright", "browser_run_code", "--stdin"],
    input=json.dumps(args, ensure_ascii=False),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("STDOUT:", result.stdout[:2500])
print("STDERR:", result.stderr[:300])
