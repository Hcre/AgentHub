#!/usr/bin/env bash
set -e

echo "=== feat-complete: 完成功能 ==="
echo ""

# 1. 跑验证
echo "── 1/6 跑验证 ──"
bash scripts/verify.sh || {
    echo ""
    echo "❌ 验证未通过，先修复再继续"
    read -r -p "按回车退出..."
    exit 1
}
echo ""

# 2. 分支检查
echo "── 2/6 分支命名检查 ──"
python scripts/check_branch.py
echo ""

# 3. 更新 roadmap
echo "── 3/6 更新 roadmap ──"
echo "请检查 spec/roadmap_开发路线图.md"
echo "完成的任务标记 ✅，追加完成日期和备注"
read -r -p "已更新? (y/n): " ok
[ "$ok" = "n" ] && { echo "请先更新 roadmap"; exit 1; }

# 4. 生成 worklog
echo ""
echo "── 4/6 写 worklog ──"
read -r -p "你的名字 (黎/董/袁): " who
read -r -p "任务描述 (如 add-ws-heartbeat): " task

python scripts/gen_worklog.py "$who" "$task" 2>/dev/null || {
    echo "⚠️ worklog 模板可能已存在，请手动编辑"
}

echo ""
echo "编辑 .agenthub/worklogs/$who 下的文件"
read -r -p "按回车继续..."

# 5. 更新 STATUS
echo ""
echo "── 5/6 更新 STATUS.md ──"
echo "请更新 .agenthub/worklogs/STATUS.md 中你那一行:"
echo "  - '正在做' 改为下个任务"
echo "  - '这周完成了' 加上本次功能"
echo "  - 更新 '最后更新' 日期"
read -r -p "已更新? (y/n): " ok
[ "$ok" = "n" ] && { echo "请先更新 STATUS.md"; exit 1; }

# 6. Commit + Push
echo ""
echo "── 6/6 Commit + Push ──"
read -r -p "Commit message (如 feat: add websocket heartbeat): " msg

git add .
git commit -m "$msg" || { echo "⚠️ commit 失败"; exit 1; }
git push origin HEAD || { echo "⚠️ push 失败"; exit 1; }

cat << 'EOF'

┌──────────────────────┐
│ ✅ feat-complete 完成 │
│ 去 GitHub 创建 PR     │
└──────────────────────┘
EOF
