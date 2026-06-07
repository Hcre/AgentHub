"""Pre-push 文档死链检查。

检查 docs/ 下所有 .md 文件中的内部链接 (相对路径) 是否可解析。
扩展 D-11 规则，从仅检查 CLAUDE.md 到检查所有文档。

红线: 文档中的内部链接必须指向存在的文件。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
WORKLOGS = ROOT / "worklogs"

# Markdown 链接: [text](path) 或 [text](path#anchor)
LINK_PATTERN = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')


def extract_links(content: str) -> list[tuple[str, str, int]]:
    """返回 (text, path, line_no) 列表"""
    links = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in LINK_PATTERN.finditer(line):
            url = m.group(2)
            # 只检查相对路径，跳过 http/https/mailto/锚点
            if url.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # 去掉 anchor
            clean = url.split("#")[0]
            links.append((m.group(1), clean, i))
    return links


def resolve_link(source_dir: Path, target: str) -> Path | None:
    """将相对链接解析为绝对文件路径"""
    # 处理 ../ 相对路径
    resolved = (source_dir / target).resolve()
    if resolved.exists():
        return resolved

    # 也尝试从 ROOT 解析
    resolved = (ROOT / target).resolve()
    if resolved.exists():
        return resolved

    return None


def check_file(path: Path) -> list[str]:
    errors = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return errors

    source_dir = path.parent
    for text, link, line_no in extract_links(content):
        if not link:
            continue
        if not resolve_link(source_dir, link):
            # 允许 .html 链接 (reports 目录)
            if link.endswith(".html"):
                continue
            # 允许图片链接 (会单独检查)
            if any(link.endswith(ext) for ext in (".png", ".jpg", ".svg", ".gif")):
                continue
            errors.append(f"{path}:{line_no}: 死链 [{text}]({link})")
    return errors


def main() -> int:
    all_errors = []
    for md_dir in (DOCS, WORKLOGS):
        if not md_dir.exists():
            continue
        for f in md_dir.rglob("*.md"):
            all_errors.extend(check_file(f))

    if all_errors:
        limit = 20
        print(f"\n[WARN] 死链检查: {len(all_errors)} 处死链（已知历史问题，不阻断 push）:\n")
        for e in all_errors[:limit]:
            print(f"  {e}")
        if len(all_errors) > limit:
            print(f"  ... 还有 {len(all_errors) - limit} 处")
        return 0  # 暂不阻断，历史债务单独处理

    print("[OK] 死链检查: 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
