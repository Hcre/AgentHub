#!/usr/bin/env python
"""Verify extracted frames are not all-black (i.e. recording captured actual content)."""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("PIL not available, install pillow")
    sys.exit(1)

frames = [
    ("C:\\Users\\yhn\\Desktop\\字节比赛\\AgentHub\\docs\\deliverables\\video\\frame-01-opening.png", "opening @10s"),
    ("C:\\Users\\yhn\\Desktop\\字节比赛\\AgentHub\\docs\\deliverables\\video\\frame-02-mid.png", "mid @100s"),
    ("C:\\Users\\yhn\\Desktop\\字节比赛\\AgentHub\\docs\\deliverables\\video\\frame-03-closing.png", "closing @190s"),
]

print(f"{'frame':30s}  {'size':14s}  {'mean_brightness':16s}  {'std':6s}  verdict")
print("-" * 100)
all_pass = True
for path, label in frames:
    p = Path(path)
    if not p.exists():
        print(f"  MISSING: {path}")
        all_pass = False
        continue
    img = Image.open(p)
    w, h = img.size
    # 缩到 100x100 然后取灰度
    g = img.convert("L").resize((100, 100))
    pixels = list(g.getdata())
    avg = sum(pixels) / len(pixels)
    var = sum((x - avg) ** 2 for x in pixels) / len(pixels)
    std = var ** 0.5
    is_dark = avg < 10 and std < 5
    is_empty = std < 3  # 单色帧
    if is_dark or is_empty:
        verdict = "FAIL (black/empty)"
        all_pass = False
    else:
        verdict = "PASS"
    print(f"  {label:28s}  {w}x{h:<6d}  {avg:8.1f}/255      {std:6.1f}  {verdict}")

print()
print("OVERALL:", "PASS" if all_pass else "FAIL")
sys.exit(0 if all_pass else 1)
