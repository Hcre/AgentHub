import subprocess, json, sys

code_js = """async (page) => {
  const claudeMsg = page.locator('p:has-text("Hero")').first();
  await claudeMsg.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Get full DOM tree of Claude S2 message
  const tree = await claudeMsg.evaluate((el) => {
    let cur = el;
    const ancestors = [];
    for (let i = 0; i < 8; i++) {
      if (!cur) break;
      const cls = (cur.className && typeof cur.className === 'string') ? cur.className.substring(0, 80) : '';
      const tag = cur.tagName;
      const r = cur.getBoundingClientRect();
      const hasOnMouseEnter = cur.onmouseenter !== null && cur.onmouseenter !== undefined;
      const hasOnMouseOver = cur.onmouseover !== null && cur.onmouseover !== undefined;
      // React 17+ uses synthetic events, not onmouseenter attribute. Use data attributes:
      const reactProps = Object.keys(cur).filter(k => k.startsWith('__reactProps') || k.startsWith('__reactEventHandlers'));
      const events = reactProps.length > 0 ? Object.keys(cur[reactProps[0]] || {}).filter(k => /mouse|hover|pointer/i.test(k)) : [];
      ancestors.push({ i, tag, cls, hasOnMouseEnter, hasOnMouseOver, reactEvents: events, x: r.x, y: r.y, w: r.width, h: r.height, hasBtns: cur.querySelectorAll('button').length });
      cur = cur.parentElement;
    }
    return ancestors;
  });

  return { tree, claudeMsgBox: await claudeMsg.boundingBox() };
}"""

args = {"code": code_js}
result = subprocess.run(
    [r"C:\Users\yhn\.mavis\bin\mavis.cmd", "mcp", "call", "playwright", "browser_run_code", "--stdin"],
    input=json.dumps(args, ensure_ascii=False),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("STDOUT:", result.stdout[:3000])
print("STDERR:", result.stderr[:300])
