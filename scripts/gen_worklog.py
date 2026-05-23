"""生成 worklog 模板文件。用法: python scripts/gen_worklog.py <你的名字> <简短描述>"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TEMPLATE = """# 工作日志：{title}

- **谁**: {who}
- **日期**: {date}
- **分支**: {branch}
- **关联 Spec**:

## 目标


## 产出
- [ ]

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| | | |

## 未完成 / 阻塞
- [ ]

## 给下一位的交接
> 写之前先查看 docs/task_assignment_v3.md，明确下游任务分配和等待对象。
>
"""


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python scripts/gen_worklog.py <你的名字> <简短描述>")
        print("示例: python scripts/gen_worklog.py 黎 fix-websocket-heartbeat")
        return 1

    who = sys.argv[1]
    desc = sys.argv[2]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    branch = get_current_branch()
    title = desc.replace("-", " ").replace("_", " ")

    content = TEMPLATE.format(
        title=title,
        who=who,
        date=today,
        branch=branch,
    )

    repo_root = Path(__file__).resolve().parent.parent
    user_dir = repo_root / ".agenthub" / "worklogs" / who
    user_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{today}_{desc}.md"
    filepath = user_dir / filename

    if filepath.exists():
        print(f"[EXISTS] {filepath}")
        return 1

    filepath.write_text(content, encoding="utf-8")
    print(f"[OK] {filepath.relative_to(repo_root)}")
    print(f"    Edit and fill content, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
