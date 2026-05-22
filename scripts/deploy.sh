#!/usr/bin/env bash
set -e

echo "=== deploy: 部署 AgentHub ==="
echo ""

# 启动 Docker (WSL)
if command -v wsl &>/dev/null && wsl --list 2>/dev/null | grep -q Ubuntu; then
    echo "► 检测到 WSL，启动 Docker..."
    wsl -d Ubuntu -u root -- bash -c "service docker start 2>/dev/null; sleep 1"
fi

# 检查 Docker
docker ps >/dev/null 2>&1 || {
    echo "► Docker daemon 未运行，尝试启动..."
    sudo service docker start 2>/dev/null || {
        echo "❌ 无法启动 Docker"
        exit 1
    }
}

echo "► 部署项目..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

docker compose -f docker/docker-compose.yml up --build -d

echo ""
echo "► 验证..."
curl -s http://localhost:8000/health
echo ""
curl -s -o /dev/null -w "Frontend HTTP %{http_code}" http://localhost:5173
echo ""

cat << 'EOF'

┌───────────────────────────┐
│ ✅ 部署完成                │
├───────────────────────────┤
│ 前端: http://localhost:5173│
│ API:  http://localhost:8000│
│ 文档: /docs                │
│ 停止: docker compose down  │
└───────────────────────────┘
EOF
