#!/usr/bin/env bash
set -e

echo "=== feat-complete: Complete Feature ==="
echo ""

# 1. Run verify
echo "-- 1/7 verify --"
bash scripts/verify.sh || {
    echo ""
    echo "[FAIL] Verification failed. Fix before continuing."
    read -r -p "Press enter..."
    exit 1
}
echo ""

# 2. Branch check
echo "-- 2/7 branch check --"
python scripts/check_branch.py
echo ""

# 3. Update roadmap
echo "-- 3/7 update roadmap --"
echo "Check spec/roadmap_开发路线图.md"
echo "Mark completed tasks with ✅, add completion date and notes."
read -r -p "Updated? (y/n): " ok
[ "$ok" = "n" ] && { echo "Update roadmap first."; exit 1; }

# 4. Write worklog
echo ""
echo "-- 4/7 write worklog --"
read -r -p "Name (黎/董/袁): " who
read -r -p "Task desc (e.g. add-ws-heartbeat): " task

python scripts/gen_worklog.py "$who" "$task" 2>/dev/null || {
    echo "[WARN] worklog may already exist, edit manually"
}

echo ""
echo "Edit file in .agenthub/worklogs/$who"
read -r -p "Press enter..."

# 5. Update STATUS
echo ""
echo "-- 5/7 update STATUS.md --"
echo "Update your row in .agenthub/worklogs/STATUS.md:"
echo "  - 'Working on' -> next task"
echo "  - 'Done this week' -> add this feature"
echo "  - Update 'Last updated' date"
read -r -p "Updated? (y/n): " ok
[ "$ok" = "n" ] && { echo "Update STATUS.md first."; exit 1; }

# 6. Commit + Push
echo ""
echo "-- 6/7 commit + push --"
read -r -p "Commit message (e.g. feat: add ws heartbeat): " msg

git add .
git commit -m "$msg" || { echo "[WARN] commit failed"; exit 1; }
git push origin HEAD || { echo "[WARN] push failed"; exit 1; }

# 7. Create PR
echo ""
echo "-- 7/7 create PR --"
read -r -p "PR title: " pr_title
read -r -p "PR summary (one line): " pr_body

gh pr create --title "$pr_title" --body "$pr_body" --base main || {
    echo "[WARN] PR creation failed"
    branch=$(git rev-parse --abbrev-ref HEAD)
    echo "Create manually: https://github.com/Hcre/AgentHub/pull/new/$branch"
}

cat << 'EOF'

========================================
feat-complete DONE
PR created. Merge after review.
Update roadmap after merge ✅
========================================
EOF
