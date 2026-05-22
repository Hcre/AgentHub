@echo off
setlocal enabledelayedexpansion

echo === AgentHub Checkpoint: Pre-Merge Smoke Test ===
echo.

set fail=0

REM 1. Health
echo [1/8] Health check...
curl -s http://localhost:8000/health | findstr "ok" >nul
if %errorlevel% neq 0 (echo [FAIL] Health & set fail=1) else echo [OK] Health

REM 2. Create Agent
echo [2/8] Create Agent...
curl -s -X POST http://localhost:8000/api/agents -H "Content-Type: application/json" -d "{\"name\":\"smoke-test-agent\",\"avatar\":\"\",\"role\":\"tester\",\"provider\":\"anthropic\",\"model\":\"test\",\"api_key\":\"sk-test\"}" | findstr "id" >nul
if %errorlevel% neq 0 (echo [FAIL] Create Agent & set fail=1) else echo [OK] Create Agent

REM 3. Create Session (need agent_id from response)
echo [3/8] Create Session...
for /f "tokens=2 delims=:" %%a in ('curl -s http://localhost:8000/api/agents ^| python -c "import sys,json;print(json.load(sys.stdin)[0]['id'])"') do set AGENT_ID=%%a
if "%AGENT_ID%"=="" (echo [FAIL] Get Agent ID & set fail=1 & goto :skip_session)
curl -s -X POST http://localhost:8000/api/sessions -H "Content-Type: application/json" -d "{\"type\":\"private\",\"agent_id\":\"%AGENT_ID%\",\"title\":\"smoke-test\"}" | findstr "id" >nul
if %errorlevel% neq 0 (echo [FAIL] Create Session & set fail=1) else echo [OK] Create Session
:skip_session

REM 4. List Sessions
echo [4/8] List Sessions...
curl -s http://localhost:8000/api/sessions | findstr "[" >nul
if %errorlevel% neq 0 (echo [FAIL] List Sessions & set fail=1) else echo [OK] List Sessions

REM 5. Search Sessions
echo [5/8] Search Sessions...
curl -s "http://localhost:8000/api/sessions?q=smoke" | findstr "[" >nul
if %errorlevel% neq 0 (echo [FAIL] Search Sessions & set fail=1) else echo [OK] Search Sessions

REM 6. Frontend
echo [6/8] Frontend...
curl -s -o nul -w "%%{http_code}" http://localhost:5173 | findstr "200" >nul
if %errorlevel% neq 0 (echo [FAIL] Frontend & set fail=1) else echo [OK] Frontend

REM 7. API Docs
echo [7/8] API Docs...
curl -s -o nul -w "%%{http_code}" http://localhost:8000/docs | findstr "200" >nul
if %errorlevel% neq 0 (echo [FAIL] API Docs & set fail=1) else echo [OK] API Docs

REM 8. verify.bat (code quality)
echo [8/8] Code quality...
call scripts\verify.bat 2>nul
if %errorlevel% neq 0 (echo [FAIL] Code quality & set fail=1) else echo [OK] Code quality

echo.
if %fail% equ 0 (
    echo ======================================
    echo [PASS] All checkpoint tests passed
    echo Ready to merge PR
    echo ======================================
) else (
    echo ======================================
    echo [FAIL] %fail% check(s) failed
    echo Fix before merging
    echo ======================================
)
exit /b %fail%
