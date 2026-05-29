#!/bin/bash
# 群组创建功能 — 后端启动脚本
# 使用方式: bash scripts/start-backend.sh

WORKTREE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MAIN_VENV="/home/huishuohuademao/workspace/AgentHub/backend/.venv"

export DATABASE_URL="postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="test"
export LLM_ADAPTER_MODE="mock"
export CORS_ORIGINS="http://localhost:5173,http://localhost:4180"

cd "$WORKTREE_DIR/src/backend"
exec "$MAIN_VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
