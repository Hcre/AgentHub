#!/bin/bash
# 群组创建功能 — 前端启动脚本
# 使用方式: bash scripts/start-frontend.sh

WORKTREE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKTREE_DIR/src/frontend"
npm run build && npm run preview -- --port 4180 --host
