"""PR-02: 分支命名检查 — 禁止直接 push 到 main，检查 feature/<domain>/<desc> 格式."""
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
        print("❌ PR-02: 禁止直接 push 到 main 分支")
        return 1

    pattern = r"^(feature|fix|refactor|docs|test|chore)/[a-z0-9]+/[a-z0-9-]+$"
    if not re.match(pattern, branch):
        print(f"❌ PR-02: 分支名 '{branch}' 不符合规范")
        print(f"   期望格式: feature/<domain>/<desc>")
        print(f"   示例: feature/chat/websocket-endpoint")
        print(f"   合法前缀: feature | fix | refactor | docs | test | chore")
        return 1

    print(f"✅ 分支名 '{branch}' 符合规范")
    return 0


if __name__ == "__main__":
    sys.exit(check_branch_name(get_current_branch()))
