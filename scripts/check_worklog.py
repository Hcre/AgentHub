"""Check worklog updated: every push with diffs must include worklog update.

Reads Git-to-person mapping from STATUS.md, then checks if the commits
being pushed include changes to the current user's worklog directory.
Exit 0 = pass, Exit 1 = fail.
"""

from __future__ import annotations

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
        capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def parse_git_mapping(content: str) -> dict[str, str]:
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
                if "待补充" not in parts[0] and "待补充" not in parts[1]:
                    mapping[parts[0]] = parts[1]
    return mapping


def get_pushed_files() -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, encoding="utf-8"
    )
    return [f.strip().replace("\\", "/") for f in result.stdout.splitlines() if f.strip()]


def has_commits_to_push() -> bool:
    result = subprocess.run(
        ["git", "rev-list", "--count", "origin/main..HEAD"],
        capture_output=True, text=True, encoding="utf-8"
    )
    count = int(result.stdout.strip())
    if count == 0:
        print("[OK] Nothing to push (already up to date)")
    return count > 0


def check_worklog_in_push(person_dir: str, pushed_files: list[str]) -> bool:
    prefix = f".agenthub/worklogs/{person_dir}/"
    for f in pushed_files:
        if f.startswith(prefix):
            print(f"[OK] Worklog in this push: {f}")
            return True
    today = get_today_str()
    print(f"[FAIL] No worklog update in {person_dir}/ included in this push")
    print(f"  Expected: .agenthub/worklogs/{person_dir}/{today}_<desc>.md")
    return False


def check_any_worklog_in_push(pushed_files: list[str]) -> bool:
    for f in pushed_files:
        if ".agenthub/worklogs/" in f and "/20" in f:
            print(f"[OK] Worklog in this push: {f}")
            return True
    today = get_today_str()
    print(f"[FAIL] No worklog update included in this push ({today})")
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

    if not has_commits_to_push():
        return 0

    pushed_files = get_pushed_files()
    git_user = get_git_user()
    content = STATUS_FILE.read_text(encoding="utf-8") if STATUS_FILE.exists() else ""
    mapping = parse_git_mapping(content)

    if git_user in mapping:
        person = mapping[git_user]
        if not check_worklog_in_push(person, pushed_files):
            errors += 1
    else:
        print(f"[WARN] Git user '{git_user}' not in STATUS.md mapping, fallback")
        if not check_any_worklog_in_push(pushed_files):
            errors += 1

    if not check_status_updated():
        errors += 1

    if errors == 0:
        print("[OK] Worklog check passed")
    else:
        print("\nAction: update your worklog and amend the commit")
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
