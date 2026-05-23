"""PR-02: Branch naming check — forbid direct push to main, validate format."""
import re
import subprocess
import sys


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def check_branch_name(branch: str) -> int:
    if branch == "main":
        print("[FAIL] PR-02: Direct push to main is forbidden. Use a feature branch.")
        return 1

    pattern = r"^(feature|fix|refactor|docs|test|chore)/[a-z0-9]+/[a-z0-9-]+$"
    if not re.match(pattern, branch):
        print(f"[FAIL] PR-02: Branch name '{branch}' does not match convention")
        print(f"   Expected: feature/<domain>/<desc>")
        print(f"   Example: feature/chat/websocket-endpoint")
        print(f"   Allowed prefixes: feature | fix | refactor | docs | test | chore")
        return 1

    print(f"[OK] Branch name '{branch}' conforms to convention")
    return 0


if __name__ == "__main__":
    sys.exit(check_branch_name(get_current_branch()))
