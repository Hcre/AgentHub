import subprocess, json, sys

code_js = """async (page) => {
  // Refresh to default S1
  await page.goto('http://127.0.0.1:5174/');
  await page.waitForTimeout(3000);

  // Find textarea in composer
  const ta = page.locator('textarea[placeholder*="Ask"]').first();
  const beforeVal = await ta.inputValue();
  const beforeDisabled = await ta.isDisabled();

  // Find and click first suggest button
  const suggestBtn = page.getByRole('button', { name: /帮我看看代码/ });
  const suggestCount = await suggestBtn.count();
  if (suggestCount === 0) return { error: 'no suggest button' };

  await suggestBtn.first().click();
  await page.waitForTimeout(500);

  const afterVal = await ta.inputValue();
  const afterDisabled = await ta.isDisabled();
  const focused = await ta.evaluate(el => el === document.activeElement);

  return { beforeVal, afterVal, afterDisabled, focused, suggestCount };
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
