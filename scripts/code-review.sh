#!/usr/bin/env bash

echo "=== code-review: 代码审查 ==="
echo ""

fail=0

echo "── 自动检查 ──"
echo ""

echo "► ruff (禁 print / 禁同步阻塞)..."
if cd backend && ruff check app/ --config pyproject.toml 2>/dev/null; then
    echo "✅ ruff 通过"
else
    echo "❌ ruff 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

echo ""
echo "► mypy 类型检查..."
if cd backend && mypy app/ 2>/dev/null; then
    echo "✅ mypy 通过"
else
    echo "❌ mypy 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

echo ""
echo "► tsc TypeScript..."
if cd frontend && npx tsc --noEmit 2>/dev/null; then
    echo "✅ tsc 通过"
else
    echo "❌ tsc 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

echo ""
echo "► eslint..."
if cd frontend && npx eslint src/ --config .eslintrc.json 2>/dev/null; then
    echo "✅ eslint 通过"
else
    echo "❌ eslint 失败"
    fail=1
fi
cd "$(dirname "$0")/.." || exit 1

echo ""
echo "► worklog 更新..."
if python scripts/check_worklog.py 2>/dev/null; then
    echo "✅ worklog 已更新"
else
    echo "❌ worklog 未更新"
    fail=1
fi

echo ""
echo "── 手动检查清单 ──"
echo ""

cat << 'EOF'
架构红线 (spec/rules/arch-rules):
🄂 AR-01 依赖倒置: L2 不 import L1/L3/L4/L5
🄂 AR-02 新 Agent 只加 Adapter
🄂 AR-03 Harness 不含 LLM 调用
🄂 AR-04 Agent 不直接通信
🄂 AR-05 Task Engine 事件溯源
🄂 AR-06 Agent 系统与模型解耦

代码红线 (spec/rules/code-rules):
🄂 CR-01 无 print()          🄂 CR-07 tsc 零错误
🄂 CR-02 无裸 SQL             🄂 CR-08 render 无 async
🄂 CR-03 必须 Alembic         🄂 CR-09 组件>200行考虑拆分
🄂 CR-04 端点有异常处理       🄂 CR-10 无硬编码密钥
🄂 CR-05 Pydantic 校验输入   🄂 CR-11 无遗留调试代码
🄂 CR-06 外部调用有超时       🄂 CR-12 禁同步阻塞 async

流程红线 (spec/rules/process-rules):
🄂 PR-02 分支命名 feature/<domain>/<desc>
🄂 PR-03 Conventional Commits
🄂 PR-04 Agent 写文件经审批
🄂 PR-07 提交前跑验证
🄂 PR-08 roadmap 已更新
🄂 PR-09 SPEC 与代码同步
EOF

echo ""
[ "$fail" -ne 0 ] && { echo "❌ 自动检查未通过"; exit 1; }

echo "✅ 自动检查通过"
echo ""
echo "逐条核对上方清单，全部通过后 PR。"
