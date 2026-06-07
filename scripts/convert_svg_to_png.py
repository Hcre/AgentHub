"""Convert SVG to PNG using Playwright.

Usage: python convert_svg_to_png.py <svg_path> <png_path>
"""
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


async def convert(svg_path: str, png_path: str) -> None:
    svg_file = Path(svg_path).resolve()
    png_file = Path(png_path).resolve()
    if not svg_file.exists():
        raise FileNotFoundError(svg_file)

    svg_content = svg_file.read_text(encoding="utf-8")
    # Wrap SVG in HTML with white background for proper PNG render
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: #ffffff; }}
  body {{ display: flex; justify-content: center; align-items: flex-start; }}
  svg {{ display: block; }}
</style>
</head>
<body>
{svg_content}
</body></html>"""

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 950}, device_scale_factor=2)
        await page.set_content(html, wait_until="networkidle")
        # Locate the SVG element and screenshot it directly
        svg_el = await page.query_selector("svg")
        if svg_el is None:
            await browser.close()
            raise RuntimeError("No SVG element found in rendered page")
        await svg_el.screenshot(path=str(png_file), omit_background=False)
        await browser.close()
    print(f"OK: {svg_file} -> {png_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: convert_svg_to_png.py <svg> <png>")
        sys.exit(1)
    asyncio.run(convert(sys.argv[1], sys.argv[2]))
