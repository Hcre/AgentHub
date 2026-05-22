@echo off
setlocal enabledelayedexpansion

echo === deploy: 部署 AgentHub ===
echo.

REM 检查 WSL
wsl --list 2>nul | findstr Ubuntu >nul
if %errorlevel% neq 0 (
    echo ❌ WSL Ubuntu 未安装，先运行: wsl --install -d Ubuntu
    pause
    exit /b 1
)

REM 进 WSL 启动 Docker
echo ► 启动 Docker...
wsl -d Ubuntu -u root -- bash -c "service docker start 2>/dev/null; sleep 1; docker ps >/dev/null 2>&1 && echo 'Docker OK' || echo 'Docker start failed'"

echo.
echo ► 部署项目...
wsl -d Ubuntu -u root -- bash -c "cd /mnt/d/AgentHub/repo && docker compose -f docker/docker-compose.yml up --build -d"

echo.
echo ► 验证...
curl -s http://localhost:8000/health 2>nul
echo.
curl -s -o nul -w "Frontend HTTP %%{http_code}" http://localhost:5173 2>nul
echo.

echo.
echo ┌───────────────────────────┐
echo │ ✅ 部署完成                │
echo ├───────────────────────────┤
echo │ 前端: http://localhost:5173│
echo │ API:  http://localhost:8000│
echo │ 文档: /docs                │
echo │ 停止: docker compose down  │
echo └───────────────────────────┘
