"""Commit-msg hook — 检查 commit message 格式。

规范:
  <type>(<scope>): <简短描述>

type: feat | fix | docs | refactor | test | chore | merge | worklog
scope: 可选，模块名或域

示例:
  ✅ feat(agents): CLI 自动扫描 PATH
  ✅ fix: opencode stdin=DEVNULL 防止卡死
  ✅ docs: 更新架构文档
  ✅ merge: feature/domain2/agent-workspace
  ✅ worklog: CLI自动扫描+Provider矩阵 (2026-05-31)
  ❌ WIP
  ❌ 修了一下
  ❌ update code
"""

import re
import sys
from pathlib import Path

VALID_TYPES = {"feat", "fix", "docs", "refactor", "test", "chore", "merge", "worklog",
               "style", "perf", "ci", "build", "revert"}

PATTERN = re.compile(
    r'^(' + '|'.join(VALID_TYPES) + r')'
    r'(\([a-zA-Z0-9_\-./]+\))?:\s*\S'
)


def main() -> int:
    # 从 .git/COMMIT_EDITMSG 或参数读取
    if len(sys.argv) > 1:
        msg_file = Path(sys.argv[1])
    else:
        msg_file = Path(".git/COMMIT_EDITMSG")

    if not msg_file.exists():
        # 非交互式提交 commit 消息通过 stdin
        print("⚠️  无法读取 commit message 文件，跳过检查")
        return 0

    lines = msg_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    # 跳过注释行
    subject = ""
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            subject = line
            break

    if not subject:
        print("❌ Commit message 为空")
        return 1

    if subject.startswith("merge") or subject.startswith("Merge"):
        return 0

    if not PATTERN.match(subject):
        print(f"\n❌ Commit message 格式错误:\n")
        print(f"  {subject}")
        print(f"\n  应为: <type>(<scope>): <描述>")
        print(f"  type: {', '.join(sorted(VALID_TYPES))}")
        print(f"  示例: feat(agents): 添加 XXX 功能")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
