"""Check worklog updated: current user has today's log + STATUS.md has today's date.

Reads Git-to-person mapping from STATUS.md to identify the pusher.
Exit 0 = pass, Exit 1 = fail.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKLOG_DIR = REPO_ROOT / ".agenthub" / "worklogs"
STATUS_FILE = WORKLOG_DIR / "STATUS.md"


def get_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_git_user() -> str:
    result = subprocess.run(
        ["git", "config", "user.name"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def parse_git_mapping(content: str) -> dict[str, str]:
    """Parse the Git-to-person mapping table from STATUS.md.

    Expected format:
    | Git用户名 | 日志目录 |
    |-----------|----------|
    | oldmanpushbike | 黎 |
    """
    mapping: dict[str, str] = {}
    in_table = False
    for line in content.splitlines():
        if "Git用户名" in line and "日志目录" in line:
            in_table = True
            continue
        if in_table:
            if not line.strip().startswith("|"):
                break
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and parts[0] not in ("Git用户名", "-----------"):
                # Skip placeholder entries like "（待补充）"
                if "待补充" not in parts[0] and "待补充" not in parts[1]:
                    mapping[parts[0]] = parts[1]
    return mapping


def check_my_worklog(person_dir: str) -> bool:
    """Check if the current user's worklog directory has today's log."""
    today = get_today_str()
    user_dir = WORKLOG_DIR / person_dir
    if not user_dir.is_dir():
        print(f"[FAIL] Worklog directory not found: {person_dir}")
        print(f"  Create it: mkdir .agenthub/worklogs/{person_dir}")
        return False
    for f in user_dir.iterdir():
        if f.suffix == ".md" and today in f.name:
            print(f"[OK] Your today worklog: {f.relative_to(REPO_ROOT)}")
            return True
    print(f"[FAIL] No worklog for today ({today}) in {person_dir}/")
    print(f"  Run: /feat-complete or write your log manually")
    return False


def check_any_worklog() -> bool:
    """Fallback: check if anyone has a worklog for today."""
    today = get_today_str()
    for d in WORKLOG_DIR.iterdir():
        if d.is_dir() and d.name not in ("template.md", "STATUS.md", ".gitkeep"):
            for f in d.iterdir():
                if f.suffix == ".md" and today in f.name:
                    print(f"[OK] Found today worklog: {f.relative_to(REPO_ROOT)}")
                    return True
    print(f"[FAIL] No worklog found for today ({today})")
    return False


def check_status_updated() -> bool:
    if not STATUS_FILE.exists():
        print("[FAIL] STATUS.md not found")
        return False
    content = STATUS_FILE.read_text(encoding="utf-8")
    today = get_today_str()
    if today in content:
        print(f"[OK] STATUS.md has today date ({today})")
        return True
    print(f"[FAIL] STATUS.md date not updated (missing {today})")
    return False


def main() -> int:
    errors = 0

    # Identify the pusher
    git_user = get_git_user()
    content = STATUS_FILE.read_text(encoding="utf-8") if STATUS_FILE.exists() else ""
    mapping = parse_git_mapping(content)

    if git_user in mapping:
        person = mapping[git_user]
        if not check_my_worklog(person):
            errors += 1
    else:
        # Fallback: git user not in mapping, check anyone has log
        print(f"[WARN] Git user '{git_user}' not in STATUS.md mapping, fallback to any-check")
        if not check_any_worklog():
            errors += 1

    if not check_status_updated():
        errors += 1

    if errors == 0:
        print("[OK] Worklog check passed")
    else:
        print(f"\nAction: 1) write your worklog  2) update STATUS.md date")
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
