import subprocess, json, sys

code_js = """async (page) => {
  // Hard reload to bypass HMR
  await page.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle' });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  // Click 群组 nav
  await page.locator('button[title="群组"]').first().click();
  await page.waitForTimeout(1500);

  // G2: state before
  const beforeH1 = await page.evaluate(() => document.querySelector('h1')?.innerText);
  const beforeUrl = page.url();

  // Find S2 article and click - try multiple approaches
  const s2Card = page.locator('article:has-text("S2")').first();
  if ((await s2Card.count()) === 0) return { error: 'S2 card not found', beforeH1, beforeUrl };

  // Approach 1: click on the title text (避开右侧 icon 区域)
  const titleSpan = s2Card.locator('text=S2 - 营销页升级').first();
  const titleExists = await titleSpan.count();
  if (titleExists > 0) {
    await titleSpan.click();
  } else {
    // Approach 2: force click on article body
    await s2Card.click({ force: true, position: { x: 100, y: 20 } });
  }
  await page.waitForTimeout(2500);

  // G2: state after
  const afterH1 = await page.evaluate(() => document.querySelector('h1')?.innerText);
  const afterUrl = page.url();
  const afterMain = await page.evaluate(() => document.querySelector('main')?.innerText?.substring(0, 500) || 'no main');

  // Now try to find Hero
  const hasHero = await page.locator(':text("Hero")').count();

  return {
    beforeH1, beforeUrl,
    afterH1, afterUrl, afterMain: afterMain.substring(0, 300),
    hasHero,
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
