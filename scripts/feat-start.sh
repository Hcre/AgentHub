#!/usr/bin/env bash
set -e

echo "=== feat-start: 开始新功能 ==="
echo ""

# 1. 同步代码
echo "► git pull..."
git pull origin main 2>/dev/null || echo "⚠️ git pull 失败，继续..."
echo ""

# 2. 分支创建
read -r -p "域名 (chat/orchestration/toolchain): " domain
read -r -p "简短描述 (如 websocket-endpoint): " desc
branch="feature/${domain}/${desc}"

echo ""
echo "创建分支: $branch"
git checkout -b "$branch" 2>/dev/null || {
    echo "⚠️ 分支已存在或创建失败，当前分支:"
    git branch --show-current
}

# 3. 生成 worklog 模板
echo ""
read -r -p "你的名字 (黎/董/袁): " who
read -r -p "任务描述 (如 add-ws-heartbeat): " task

python scripts/gen_worklog.py "$who" "$task" 2>/dev/null || {
    echo "⚠️ worklog 生成失败，手动执行: python scripts/gen_worklog.py $who $task"
}

# 4. 提醒
cat << 'EOF'

┌──────────────────────────────────────┐
│ ✅ feat-start 完成                     │
├──────────────────────────────────────┤
│ 接下来:                                │
│ 1. 读相关 SPEC (见 skills/feat-start)  │
│ 2. 编辑 worklog                        │
│ 3. 更新 STATUS.md 中你的行              │
│ 4. 开始开发                             │
│ 完成后运行: scripts/feat-complete.sh    │
└──────────────────────────────────────┘
EOF
