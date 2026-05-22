@echo off
setlocal enabledelayedexpansion

echo === feat-start: 开始新功能 ===
echo.

REM 1. 同步代码
echo ► git pull...
git pull origin main 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ git pull 失败，继续...
)
echo.

REM 2. 分支创建
set /p domain="域名 (chat/orchestration/toolchain): "
set /p desc="简短描述 (如 websocket-endpoint): "
set branch=feature/%domain%/%desc%

echo.
echo 创建分支: %branch%
git checkout -b %branch% 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ 分支已存在或创建失败，检查当前分支
    git branch --show-current
) else (
    echo ✅ 分支已创建: %branch%
)

REM 3. 生成 worklog 模板
echo.
set /p who="你的名字 (黎/董/袁): "
set /p task="任务描述 (如 add-ws-heartbeat): "

python scripts/gen_worklog.py %who% %task% 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ worklog 生成失败，请手动执行: python scripts\gen_worklog.py %who% %task%
) else (
    echo ✅ worklog 模板已生成
)

REM 4. 提醒
echo.
echo ┌─────────────────────────────────────┐
echo │ ✅ feat-start 完成                    │
echo ├─────────────────────────────────────┤
echo │ 接下来:                               │
echo │ 1. 读相关 SPEC (见 skills/feat-start) │
echo │ 2. 编辑 worklog                        │
echo │ 3. 更新 STATUS.md 中你的行             │
echo │ 4. 开始开发                            │
echo │ 完成后运行: scripts\feat-complete.bat  │
echo └─────────────────────────────────────┘
