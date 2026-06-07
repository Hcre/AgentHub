async (page) => {
  // Hover 第一条群聊消息看 Pin/复制代码按钮是否出现
  const msg = page.locator('article').first();
  if ((await msg.count()) === 0) return { error: 'no article' };

  // Before hover
  const before = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('button'));
    return all.map(b => (b.title || b.getAttribute('aria-label') || b.innerText || '').substring(0, 30)).filter(t => t).slice(0, 30);
  });

  // Hover message center
  const box = await msg.boundingBox();
  if (!box) return { error: 'no bbox' };
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(500);

  // After hover
  const after = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('button'));
    return all.map(b => (b.title || b.getAttribute('aria-label') || b.innerText || '').substring(0, 30)).filter(t => t).slice(0, 30);
  });

  // New buttons added
  const newBtns = after.filter(b => !before.includes(b));
  return { before: before.length, after: after.length, newBtns, msgBox: { x: box.x, y: box.y, w: box.width, h: box.height } };
}
