@echo off
setlocal enabledelayedexpansion

echo === code-review: 代码审查 ===
echo.

set fail=0

REM 自动检查
echo ── 自动检查 ──
echo.

echo ► ruff (禁 print / 禁同步阻塞)...
cd /d "%~dp0..\backend"
ruff check app/ --config pyproject.toml 2>nul
if %errorlevel% neq 0 (echo ❌ ruff 失败 & set fail=1) else echo ✅ ruff 通过
cd /d "%~dp0.."

echo.
echo ► mypy 类型检查...
cd /d "%~dp0..\backend"
mypy app/ 2>nul
if %errorlevel% neq 0 (echo ❌ mypy 失败 & set fail=1) else echo ✅ mypy 通过
cd /d "%~dp0.."

echo.
echo ► tsc TypeScript...
cd /d "%~dp0..\frontend"
call npx tsc --noEmit 2>nul
if %errorlevel% neq 0 (echo ❌ tsc 失败 & set fail=1) else echo ✅ tsc 通过
cd /d "%~dp0.."

echo.
echo ► eslint...
cd /d "%~dp0..\frontend"
call npx eslint src/ --config .eslintrc.json 2>nul
if %errorlevel% neq 0 (echo ❌ eslint 失败 & set fail=1) else echo ✅ eslint 通过
cd /d "%~dp0.."

echo.
echo ► worklog 更新...
python scripts/check_worklog.py 2>nul
if %errorlevel% neq 0 (echo ❌ worklog 未更新 & set fail=1) else echo ✅ worklog 已更新

echo.
echo ── 手动检查清单 ──
echo.
echo 架构红线 (conventions/01-architecture):
echo 🄂 AR-01 依赖倒置: L2 不 import L1/L3/L4/L5
echo 🄂 AR-02 新 Agent 只加 Adapter
echo 🄂 AR-03 Harness 不含 LLM 调用
echo 🄂 AR-04 Agent 不直接通信
echo 🄂 AR-05 Task Engine 事件溯源
echo 🄂 AR-06 Agent 系统与模型解耦
echo.
echo 代码红线 (conventions/02-coding):
echo 🄂 CR-01 无 print()         🄂 CR-07 tsc 零错误
echo 🄂 CR-02 无裸 SQL            🄂 CR-08 render 无 async
echo 🄂 CR-03 必须 Alembic        🄂 CR-09 组件>200行考虑拆分
echo 🄂 CR-04 端点有异常处理      🄂 CR-10 无硬编码密钥
echo 🄂 CR-05 Pydantic 校验输入  🄂 CR-11 无遗留调试代码
echo 🄂 CR-06 外部调用有超时      🄂 CR-12 禁同步阻塞 async
echo.
echo 流程红线 (conventions/99-process-rules):
echo 🄂 PR-02 分支命名 feature/<domain>/<desc>
echo 🄂 PR-03 Conventional Commits
echo 🄂 PR-04 Agent 写文件经审批
echo 🄂 PR-07 提交前跑验证
echo 🄂 PR-08 roadmap 已更新
echo 🄂 PR-09 SPEC 与代码同步
echo.

if %fail% neq 0 (
    echo ❌ 自动检查未通过
    exit /b 1
) else (
    echo ✅ 自动检查通过
)
echo.
echo 逐条核对上方清单，全部通过后 PR。
