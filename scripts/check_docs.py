"""Document structure check (pre-push hook).

Checks:
  1. docs/ root naming: {English}_{Chinese}.md
  2. docs/explore/ root: EXP-NN_ / ADR-NN- / README / EVOLUTION
  3. docs/explore/ personal subdirs: {黎,董,袁}/topic.md
  4. docs/archive/ naming: DEPRECATED_ prefix
  5. worklogs/ naming: YYYY-MM-DD_ prefix
  6. No version suffixes (_vNN, _final, _new, _old)
  7. No .html files in docs/
  8. CLAUDE.md references all resolve
  9. pre-commit hooks are installed
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# -- Naming patterns --

DOCS_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*_.+\.md$")
EXPLORE_ROOT_PATTERNS = {
    "EXP": re.compile(r"^EXP-\d{2}_.+\.md$"),
    "ADR": re.compile(r"^ADR-\d{2}-[a-z0-9-]+\.md$"),
    "special": {"README.md", "EVOLUTION.md"},
}
EXPLORE_MEMBERS = {"黎", "董", "袁"}
ARCHIVE_PATTERN = re.compile(r"^DEPRECATED_.+\.md$")
WORKLOG_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_.+\.md$")
WORKLOG_SPECIAL = {"STATUS.md", "template.md"}
VERSION_SUFFIX = re.compile(r"_(v\d+|final|最新|old|new|副本)")

errors: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)


# 1. docs/ root
docs_root = ROOT / "docs"
if docs_root.is_dir():
    for f in docs_root.iterdir():
        if f.is_dir():
            continue
        if f.suffix == ".html":
            error(f"docs/{f.name}: HTML files should not be committed (markdown is source)")
            continue
        if f.suffix != ".md":
            continue
        if VERSION_SUFFIX.search(f.stem):
            error(f"docs/{f.name}: filename contains version suffix (_vN/_final/...), archive it")
        if not DOCS_PATTERN.match(f.name):
            error(
                f"docs/{f.name}: naming must be {{English}}_{{Chinese}}.md, "
                f"e.g. PRD_AgentHub_xxx.md"
            )

# 2. docs/explore/
explore_dir = docs_root / "explore"
if explore_dir.is_dir():
    for f in explore_dir.iterdir():
        if f.is_dir():
            # Personal subdirectory: check it's a known member
            if f.name not in EXPLORE_MEMBERS:
                error(
                    f"docs/explore/{f.name}/: unknown personal directory, "
                    f"allowed: {', '.join(sorted(EXPLORE_MEMBERS))}"
                )
                continue
            # Check files inside personal subdir
            for sub in f.iterdir():
                if sub.suffix != ".md":
                    continue
                if VERSION_SUFFIX.search(sub.stem):
                    error(
                        f"docs/explore/{f.name}/{sub.name}: "
                        f"filename contains version suffix"
                    )
            continue
        if f.suffix != ".md":
            continue
        name = f.name
        if name in EXPLORE_ROOT_PATTERNS["special"]:
            continue
        if EXPLORE_ROOT_PATTERNS["EXP"].match(name):
            continue
        if EXPLORE_ROOT_PATTERNS["ADR"].match(name):
            continue
        error(
            f"docs/explore/{name}: must be EXP-NN_{{desc}}.md / ADR-NN-{{slug}}.md "
            f"/ README.md / EVOLUTION.md, or put in personal subdirectory (黎/董/袁/)"
        )

# 3. docs/archive/
archive_dir = docs_root / "archive"
if archive_dir.is_dir():
    for f in archive_dir.iterdir():
        if f.is_dir():
            continue
        if f.suffix != ".md":
            continue
        if not ARCHIVE_PATTERN.match(f.name):
            error(f"docs/archive/{f.name}: missing DEPRECATED_ prefix")

# 4. worklogs/
worklogs_dir = ROOT / "worklogs"
if worklogs_dir.is_dir():
    for f in worklogs_dir.iterdir():
        if f.is_dir():
            for sub in f.iterdir():
                if sub.suffix != ".md":
                    continue
                if sub.name in WORKLOG_SPECIAL:
                    continue
                if not WORKLOG_PATTERN.match(sub.name):
                    error(
                        f"worklogs/{f.name}/{sub.name}: "
                        f"worklog must start with YYYY-MM-DD_"
                    )
        else:
            if f.suffix != ".md":
                continue
            if f.name in WORKLOG_SPECIAL:
                continue
            if not WORKLOG_PATTERN.match(f.name):
                error(
                    f"worklogs/{f.name}: "
                    f"worklog must start with YYYY-MM-DD_ (or move to docs/explore/)"
                )

# 5. No .html in docs/ tree
for html_file in ROOT.glob("docs/**/*.html"):
    rel = html_file.relative_to(ROOT)
    error(f"{rel}: HTML files should not be committed, markdown is source")

# 6. No version suffix in docs/ (except archive/)
for md_file in ROOT.glob("docs/**/*.md"):
    rel = str(md_file.relative_to(ROOT))
    if "archive" in md_file.parts:
        continue
    if VERSION_SUFFIX.search(md_file.stem):
        error(f"{rel}: filename contains version suffix, archive to docs/archive/")

# 7. CLAUDE.md path references
claude_md = ROOT / "CLAUDE.md"
if claude_md.is_file():
    content = claude_md.read_text(encoding="utf-8")
    refs = re.findall(r"`([^`]+\.md)`", content)
    for ref in refs:
        if "<" in ref or ">" in ref:
            continue
        link_match = re.match(r"\[.*\]\((.+)\)", ref)
        if link_match:
            ref = link_match.group(1)
        resolved = ROOT / ref
        if not resolved.exists():
            error(f"CLAUDE.md references missing file: `{ref}`")

# 8. Pre-commit hooks installed
hooks_dir = ROOT / ".git" / "hooks"
for hook_name in ["pre-commit", "pre-push"]:
    hook_file = hooks_dir / hook_name
    if not hook_file.exists():
        error(
            f".git/hooks/{hook_name} not installed. "
            f"Run: pre-commit install --hook-type pre-push && pre-commit install"
        )
    elif hook_file.stat().st_size < 100:
        # Sample files are small; real pre-commit hooks are larger
        error(
            f".git/hooks/{hook_name} appears to be a sample. "
            f"Run: pre-commit install --hook-type pre-push && pre-commit install"
        )

# -- Output --

if errors:
    print(f"\nFAIL: doc check failed ({len(errors)} issues):\n")
    for e in sorted(errors):
        print(f"  - {e}")
    print(f"\n  Run /doc-sync to fix.\n")
    sys.exit(1)
else:
    print("OK: doc check passed")
    sys.exit(0)
