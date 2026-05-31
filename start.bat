@echo off
chcp 65001 >nul
title AgentHub
setlocal enabledelayedexpansion

echo.
echo   ========================================
echo         AgentHub 正在启动...
echo   ========================================
echo.

cd /d "%~dp0"

:: ── 安装后端依赖 ──
if not exist "backend\.venv" (
    echo [1/4] 创建 Python 虚拟环境...
    python -m venv backend\.venv
)
call backend\.venv\Scripts\activate.bat
pip install -q -r backend\requirements.txt 2>nul

:: ── 数据库（优先 Docker PG，不可用时 SQLite） ──
docker ps >nul 2>&1
if %errorlevel% equ 0 (
    docker compose -f docker/docker-compose.yml up -d postgres redis 2>nul
    set DB_URL=postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub
    set REDIS_URL=redis://localhost:6379/0
    echo [2/4] PostgreSQL + Redis ^(Docker^)
) else (
    set DB_URL=sqlite+aiosqlite:///./agenthub.db
    set REDIS_URL=
    echo [2/4] SQLite ^(本地模式^)
)

:: ── 数据库迁移 ──
cd backend
alembic upgrade head 2>nul
cd ..

:: ── 启动后端 ──
echo [3/4] 启动后端 (http://localhost:9000)...
start "AgentHub Backend" /min cmd /c "cd /d %~dp0backend && ..\backend\.venv\Scripts\activate && set DATABASE_URL=%DB_URL% && set REDIS_URL=%REDIS_URL% && python -m uvicorn app.main:app --host 0.0.0.0 --port 9000"

:: ── 启动前端 ──
echo [4/4] 启动前端 (http://localhost:5173)...
if not exist "frontend\node_modules" (
    echo   安装前端依赖...
    cd frontend && call npm install && cd ..
)
start "AgentHub Frontend" /min cmd /c "cd /d %~dp0frontend && npm run dev"

:: ── 等待后打开浏览器 ──
echo   等待服务启动...
timeout /t 6 /nobreak >nul
start http://localhost:5173

echo.
echo   ========================================
echo    启动完成！
echo    前端: http://localhost:5173
echo    后端: http://localhost:9000/docs
echo   ========================================
echo.
echo   关闭此窗口不会停止服务。
echo   要停止，请关闭 "AgentHub" 开头的命令行窗口。
echo.

timeout /t 5 /nobreak >nul
