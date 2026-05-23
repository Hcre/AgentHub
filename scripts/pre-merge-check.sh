#!/usr/bin/env bash
# pre-merge-check.sh — 合并前强制差异审查
# 用法: ./scripts/pre-merge-check.sh [target-branch]
# 默认 target: main
#
# 此脚本由 CLAUDE.md「合并前审查」规则强制执行。
# Claude Code 会在 git merge / gh pr create 前自动调用。

set -euo pipefail

TARGET="${1:-main}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$REPO_ROOT"

echo "================================================"
echo "  pre-merge-check: 审查与 $TARGET 的差异"
echo "================================================"
echo ""

# 1. branch 确认
CURRENT_BRANCH=$(git branch --show-current)
echo "当前分支: $CURRENT_BRANCH"
echo "目标分支: $TARGET"
echo ""

# 2. 文件级变更概览
echo "--- 文件变更清单 ---"
git diff --stat "$TARGET"...HEAD 2>/dev/null || git diff --stat "$TARGET"...HEAD 2>/dev/null || {
    echo "WARNING: 无法计算 $TARGET...HEAD 的差异，尝试 fetch..."
    git fetch origin "$TARGET" 2>/dev/null || true
    git diff --stat "origin/$TARGET"...HEAD 2>/dev/null || echo "ERROR: 仍然无法计算差异，请手动检查"
}
echo ""

# 3. 新增/删除文件
echo "--- 新增文件 ---"
git diff --name-status "$TARGET"...HEAD 2>/dev/null | grep "^A" || echo "(无)"
echo ""
echo "--- 删除文件 ---"
git diff --name-status "$TARGET"...HEAD 2>/dev/null | grep "^D" || echo "(无)"
echo ""

# 4. 检查不应提交的文件
echo "--- 安全检查 ---"
BAD_FILES=(
    ".claude/settings.local.json"
    ".env"
    ".env.local"
    "*.pyc"
    "__pycache__"
)
for pattern in "${BAD_FILES[@]}"; do
    FOUND=$(git diff --name-only "$TARGET"...HEAD 2>/dev/null | grep "$pattern" || true)
    if [ -n "$FOUND" ]; then
        echo "⚠️  WARNING: 以下文件不应提交: $FOUND"
    fi
done
echo ""

# 5. 输出结论
echo "================================================"
echo "  审查完成。请逐文件确认上述差异。"
echo "  禁止跳过此步骤直接合并。"
echo "================================================"
