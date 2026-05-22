@echo off
setlocal enabledelayedexpansion

echo === feat-complete: Complete Feature ===
echo.

REM 1. Run verify
echo -- 1/7 verify --
call scripts\verify.bat
if %errorlevel% neq 0 (
    echo.
    echo [FAIL] Verification failed. Fix before continuing.
    pause
    exit /b 1
)
echo.

REM 2. Branch check
echo -- 2/7 branch check --
python scripts/check_branch.py
echo.

REM 3. Update roadmap
echo -- 3/7 update roadmap --
echo Check spec/roadmap_开发路线图.md
echo Mark completed tasks with ✅, add completion date and notes.
echo.
set /p roadmap_ok="Updated? (y/n): "
if /i "%roadmap_ok%"=="n" (
    echo Update roadmap first.
    pause
    exit /b 1
)

REM 4. Write worklog
echo.
echo -- 4/7 write worklog --
set /p who="Name (黎/董/袁): "
set /p task="Task desc (e.g. add-ws-heartbeat): "

python scripts/gen_worklog.py %who% %task% 2>nul
if %errorlevel% neq 0 (
    echo [WARN] worklog may already exist, edit manually
) else (
    echo [OK] worklog template generated
)
echo.
echo Edit file in .agenthub/worklogs/%who%
pause

REM 5. Update STATUS
echo.
echo -- 5/7 update STATUS.md --
echo Update your row in .agenthub/worklogs/STATUS.md:
echo   - "Working on" -> next task
echo   - "Done this week" -> add this feature
echo   - Update "Last updated" date
echo.
set /p status_ok="Updated? (y/n): "
if /i "%status_ok%"=="n" (
    echo Update STATUS.md first.
    pause
    exit /b 1
)

REM 6. Commit + Push
echo.
echo -- 6/7 commit + push --
set /p msg="Commit message (e.g. feat: add ws heartbeat): "

git add .
git commit -m "%msg%"
if %errorlevel% neq 0 (
    echo [WARN] commit failed
    pause
    exit /b 1
)

git push origin HEAD
if %errorlevel% neq 0 (
    echo [WARN] push failed
    pause
    exit /b 1
)

REM 7. Create PR
echo.
echo -- 7/7 create PR --
set /p pr_title="PR title: "
set /p pr_body="PR summary (one line): "

gh pr create --title "!pr_title!" --body "!pr_body!" --base main
if %errorlevel% neq 0 (
    echo [WARN] PR creation failed
    echo Create manually: https://github.com/Hcre/AgentHub/pull/new/%branch%
)

echo.
echo ========================================
echo feat-complete DONE
echo PR created. Merge after review.
echo Update roadmap after merge ✅
echo ========================================
