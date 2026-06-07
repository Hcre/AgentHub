import subprocess, json, sys

code_js = """async (page) => {
  const claudeMsg = page.locator('p:has-text("Hero")').first();
  await claudeMsg.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Find group/msg ancestor
  const groupMsg = claudeMsg.locator('xpath=ancestor::div[contains(@class, "group/msg")][1]');
  const cnt = await groupMsg.count();
  if (cnt === 0) return { error: 'no group/msg' };

  // Get all descendants with their classes
  const allChildren = await groupMsg.evaluate((el) => {
    function walk(e, depth) {
      const r = [];
      const cls = (e.className && typeof e.className === 'string') ? e.className : '';
      const tag = e.tagName;
      r.push({ depth, tag, cls: cls.substring(0, 100), text: (e.innerText || '').substring(0, 40), btns: e.querySelectorAll('button').length });
      if (depth < 5) {
        for (const c of e.children) {
          r.push(...walk(c, depth + 1));
        }
      }
      return r;
    }
    return walk(el, 0);
  });

  return { tree: allChildren };
}"""

args = {"code": code_js}
result = subprocess.run(
    [r"C:\Users\yhn\.mavis\bin\mavis.cmd", "mcp", "call", "playwright", "browser_run_code", "--stdin"],
    input=json.dumps(args, ensure_ascii=False),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("STDOUT:", result.stdout[:4000])
print("STDERR:", result.stderr[:300])
