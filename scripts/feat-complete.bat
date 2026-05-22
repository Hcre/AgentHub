@echo off
setlocal enabledelayedexpansion

echo === feat-complete: 完成功能 ===
echo.

REM 1. 跑验证
echo ── 1/6 跑验证 ──
call scripts\verify.bat
if %errorlevel% neq 0 (
    echo.
    echo ❌ 验证未通过，先修复再继续
    pause
    exit /b 1
)
echo.

REM 2. 分支检查
echo ── 2/6 分支命名检查 ──
python scripts/check_branch.py
echo.

REM 3. 更新 roadmap 提醒
echo ── 3/6 更新 roadmap ──
echo 请检查 spec/roadmap_开发路线图.md
echo 完成的任务标记 ✅，追加完成日期和备注
echo.
set /p roadmap_ok="已更新? (y/n): "
if /i "%roadmap_ok%"=="n" (
    echo 请先更新 roadmap 再继续
    pause
    exit /b 1
)

REM 4. 生成 worklog
echo.
echo ── 4/6 写 worklog ──
set /p who="你的名字 (黎/董/袁): "
set /p task="任务描述 (如 add-ws-heartbeat): "

python scripts/gen_worklog.py %who% %task% 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ worklog 模板可能已存在，请手动编辑或生成
) else (
    echo ✅ worklog 模板已生成，请编辑填写内容
)
echo.
echo 编辑 .agenthub/worklogs/%who% 下的文件
pause

REM 5. 更新 STATUS
echo.
echo ── 5/6 更新 STATUS.md ──
echo 请更新 .agenthub/worklogs/STATUS.md 中你那一行:
echo   - "正在做" 改为下个任务
echo   - "这周完成了" 加上本次功能
echo   - 更新"最后更新"日期
echo.
set /p status_ok="已更新? (y/n): "
if /i "%status_ok%"=="n" (
    echo 请先更新 STATUS.md 再继续
    pause
    exit /b 1
)

REM 6. Commit + Push
echo.
echo ── 6/6 Commit + Push ──
set /p msg="Commit message (如 feat: add websocket heartbeat): "

git add .
git commit -m "%msg%"
if %errorlevel% neq 0 (
    echo ⚠️ commit 失败
    pause
    exit /b 1
)

git push origin %branch%
if %errorlevel% neq 0 (
    echo ⚠️ push 失败
    pause
    exit /b 1
)

echo.
echo ┌──────────────────────┐
echo │ ✅ feat-complete 完成 │
echo │ 去 GitHub 创建 PR     │
echo └──────────────────────┘
