"""检查 worklog 是否已更新：当前日期 + STATUS.md 最后修改时间.
Exit 0 = 通过, Exit 1 = 未更新.
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKLOG_DIR = REPO_ROOT / ".agenthub" / "worklogs"
STATUS_FILE = WORKLOG_DIR / "STATUS.md"


def get_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_today_worklog_exists() -> bool:
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
    if not check_today_worklog_exists():
        errors += 1
    if not check_status_updated():
        errors += 1
    if errors == 0:
        print("[OK] Worklog check passed")
    else:
        print(f"\nAction: 1) write worklog  2) update STATUS.md date")
    return 1 if errors > 0 else 0
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
