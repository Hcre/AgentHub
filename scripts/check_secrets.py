"""Pre-push 密钥泄露扫描。

检查规则:
- sk- 开头的 API key (长度 20+)
- 明显的 token/key/secret 赋值
- 排除注释、文档、测试 fixture

红线: 代码中不得出现硬编码密钥。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 匹配模式
PATTERNS = [
    (r'sk-[a-zA-Z0-9]{20,}', "API Key (sk-xxx)"),
    (r'(?i)(api_key|apikey|secret|token|password)\s*[:=]\s*["\'](?![${<])([a-zA-Z0-9\-_]{16,})["\']',
     "硬编码密钥/密码"),
]

# 排除目录
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv", "dist", "build",
             ".claude", "archive", ".mypy_cache", ".pytest_cache"}

# 允许出现 API key 的目录（测试 fixture、mock 数据、配置模板）
ALLOW_DIRS = {"tests", "docs", "worklogs", "scripts"}


def is_allowed(path: Path) -> bool:
    parts = path.parts
    for d in ALLOW_DIRS:
        if d in parts:
            return True
    return False


def check_file(path: Path) -> list[str]:
    errors = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return errors

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        # 跳过注释行
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("--"):
            continue
        for pattern, desc in PATTERNS:
            m = re.search(pattern, stripped)
            if m:
                # 排除 {env:XXX} / $env:XXX 等占位符引用
                full = m.group(0)
                if "{env" in full or "${" in full:
                    continue
                # 排除明显是示例/占位符的
                if "your-key" in full.lower() or "xxxx" in full.lower() or "example" in full.lower():
                    continue
                errors.append(f"{path}:{i}: {desc} → {full[:60]}")
    return errors


def main() -> int:
    all_errors = []
    for f in ROOT.rglob("*"):
        if f.is_dir() or any(d in f.parts for d in SKIP_DIRS):
            continue
        if f.suffix in (".py", ".ts", ".tsx", ".js", ".json", ".jsonc", ".yaml", ".yml", ".toml", ".sh", ".env"):
            if is_allowed(f):
                continue
            all_errors.extend(check_file(f))

    if all_errors:
        print(f"\n[FAIL] 密钥泄露扫描: {len(all_errors)} 处疑似硬编码密钥:\n")
        for e in all_errors[:10]:
            print(f"  {e}")
        if len(all_errors) > 10:
            print(f"  ... 还有 {len(all_errors) - 10} 处")
        print("\n  密钥应通过环境变量或加密存储传入，不应硬编码在代码中。")
        return 1

    print("[OK] 密钥泄露扫描: 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
