#!/usr/bin/env bash
set -e

echo "=== AgentHub 验证检查 ==="
echo ""

fail=0

# 后端: ruff lint
echo "► 后端 ruff lint..."
if cd src/backend && ruff check app/ --config pyproject.toml; then
    echo "✅ ruff 通过"
else
    echo "❌ ruff 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

# 后端: ruff format 检查
echo ""
echo "► 后端 ruff format..."
if cd src/backend && ruff format --check app/ --config pyproject.toml; then
    echo "✅ ruff format 通过"
else
    echo "❌ ruff format 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

# 后端: mypy
echo ""
echo "► 后端 mypy..."
if cd src/backend && mypy app/; then
    echo "✅ mypy 通过"
else
    echo "❌ mypy 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

# 前端: tsc typecheck
echo ""
echo "► 前端 TypeScript..."
if cd src/frontend && npx tsc --noEmit; then
    echo "✅ tsc 通过"
else
    echo "❌ tsc 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

# 前端: eslint
echo ""
echo "► 前端 eslint..."
if cd src/frontend && npx eslint src/ --config .eslintrc.json; then
    echo "✅ eslint 通过"
else
    echo "❌ eslint 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

# 日志: worklog 更新检查
echo ""
echo "► worklog 更新检查..."
if python scripts/check_worklog.py; then
    echo "✅ worklog 已更新"
else
    echo "❌ worklog 未更新"
    fail=1
fi

echo ""
if [ "$fail" -eq 0 ]; then
    echo "🎉 全部通过"
else
    echo "❌ 有检查未通过，请修复后再提交"
fi
exit "$fail"
