@echo off
setlocal enabledelayedexpansion

echo === AgentHub 验证检查 ===
echo.

set fail=0

REM 后端: ruff lint
echo ► 后端 ruff lint...
cd /d "%~dp0..\backend"
ruff check app/ --config pyproject.toml
if %errorlevel% neq 0 (
    echo ❌ ruff 失败
    set fail=1
) else (
    echo ✅ ruff 通过
)
cd /d "%~dp0.."

REM 后端: ruff format
echo.
echo ► 后端 ruff format...
cd /d "%~dp0..\backend"
ruff format --check app/ --config pyproject.toml
if %errorlevel% neq 0 (
    echo ❌ ruff format 失败
    set fail=1
) else (
    echo ✅ ruff format 通过
)
cd /d "%~dp0.."

REM 后端: mypy
echo.
echo ► 后端 mypy...
cd /d "%~dp0..\backend"
mypy app/
if %errorlevel% neq 0 (
    echo ❌ mypy 失败
    set fail=1
) else (
    echo ✅ mypy 通过
)
cd /d "%~dp0.."

REM 前端: tsc typecheck
echo.
echo ► 前端 TypeScript...
cd /d "%~dp0..\frontend"
call npx tsc --noEmit
if %errorlevel% neq 0 (
    echo ❌ tsc 失败
    set fail=1
) else (
    echo ✅ tsc 通过
)
cd /d "%~dp0.."

REM 前端: eslint
echo.
echo ► 前端 eslint...
cd /d "%~dp0..\frontend"
call npx eslint src/ --config .eslintrc.json
if %errorlevel% neq 0 (
    echo ❌ eslint 失败
    set fail=1
) else (
    echo ✅ eslint 通过
)
cd /d "%~dp0.."

echo.
if %fail% equ 0 (
    echo 🎉 全部通过
) else (
    echo ❌ 有检查未通过，请修复后再提交
)
exit /b %fail%
