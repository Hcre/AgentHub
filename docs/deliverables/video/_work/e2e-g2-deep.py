import subprocess, json, sys

code_js = """async (page) => {
  // Cache-busting query
  const t = Date.now();
  await page.goto(`http://127.0.0.1:5174/?_t=${t}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.locator('button[title="群组"]').first().click();
  await page.waitForTimeout(2000);

  // Inspect article DOM
  const articleInfo = await page.evaluate(() => {
    const arts = document.querySelectorAll('article');
    if (arts.length === 0) return { count: 0 };
    const a = arts[0];
    return {
      count: arts.length,
      className: a.className,
      hasOnClick: !!a.onclick,
      // React onClick stored in __reactProps
      reactKeys: Object.keys(a).filter(k => k.startsWith('__react')),
      hasCursorPointer: a.className.includes('cursor-pointer'),
    };
  });

  // Try direct JS click via dispatchEvent
  const directClickResult = await page.evaluate(() => {
    const a = document.querySelector('article');
    if (!a) return 'no article';
    // Native click - this should fire onClick
    a.click();
    return 'native clicked';
  });
  await page.waitForTimeout(1500);
  const h1AfterJsClick = await page.evaluate(() => document.querySelector('h1')?.innerText);

  // Try again with React event - React 16+ uses synthetic events but native click should propagate
  const dispatchResult = await page.evaluate(() => {
    const a = document.querySelector('article');
    if (!a) return 'no article';
    // Click in middle of article (avoiding any nested stopPropagation)
    const r = a.getBoundingClientRect();
    const target = document.elementFromPoint(r.left + 50, r.top + 20);
    if (target) target.click();
    return { targetTag: target?.tagName, targetClass: target?.className?.substring(0, 50) };
  });
  await page.waitForTimeout(1500);
  const h1AfterDispatch = await page.evaluate(() => document.querySelector('h1')?.innerText);

  return { articleInfo, directClickResult, h1AfterJsClick, dispatchResult, h1AfterDispatch };
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
