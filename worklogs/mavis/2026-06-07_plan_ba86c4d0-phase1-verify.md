# 2026-06-07 plan_ba86c4d0 强收 Phase 1 实测校正

> **Session 时间**: 2026-06-07 19:39 - 19:50
> **owner**: Mavis（mvs_ee3d79d9bfb44a02b6dacda1d8d47f71）
> **触发**: user 怀疑"STATUS 写得很漂亮但代码真在跑吗？"要求做真机 E2E 验证
> **关联 ADR**: [0014 plan_ba86c4d0 强收](..\decisions\0014-mavis-team-plan-ba86c4d0-strong-close.md)（待追加 Phase 1 校正段）

## 1. Phase 1 验证（无 UI，纯代码 + git + pytest）

### 1a. git log 验证 20 commit 都在 main ✅

`git log --oneline -25` 输出确认 20 commit 全部在 main，HEAD eea1d0e 是 ci 最后一个 commit。

### 1b. 文件存在 + 行号验证（部分有偏差）

| STATUS 写的 | 实际 | 评估 |
|------------|------|------|
| `WebPreviewCard.tsx:80` iframe sandbox | 实际 line 106 + 109（全屏）+ 168 + 171（展开）| ❌ 行号错，line 80 是 `</div>` 闭合标签 |
| `MessageBubble.tsx:155-188` Pin | 实际 togglePin 从 line 176 开始到 ~210+ | ❌ 范围错位（155-188 跨 copy code catch + regenerate + reply + pin 开头）|
| `MessageBubble.tsx:112-144` handleCopyCode | 112 是注释行，函数体 129-161 | ⚠️ 范围接近对，但 112 不是函数起点 |
| `DiffView.tsx:29-41` 彩色 emerald/rose | 实际 29-41 行 emerald/rose RGBA 配置 | ✅ 完全对 |
| `attachments.py:99-158` 10MiB + 7 MIME | 99 是 router 定义，上传 endpoint 102-158 | ⚠️ 范围基本对 |
| `seed_demo_data.py` | 实际在 `src/backend/scripts/seed_demo_data.py` | ✅ 存在（不在 src/frontend）|
| `MonacoEditor.tsx` frontend-p2 c2d2a59 | 实际在 `src/frontend/src/components/editor/MonacoEditor.tsx` | ✅ 存在 |
| `ci.yml` | 实际在 `.github/workflows/ci.yml` | ✅ 存在 |
| 9 个文档沉淀文件 (architecture-diagram.svg, er-diagram.svg, commands-reference.md) | 存在 docs/specs/04-commands + docs/roadmap/architecture 等 | ✅ 存在 |

**结论**：文件都在，行号大致范围对但精确度不够（**STATUS 描述不严谨**）。

### 1c. 3 known gap 实测校正 ⚠️ **重大发现**

#### P0-4 Pin session 校验 — STATUS 描述基本对

- `src/backend/app/api/routers/sessions.py:87-122` 真实有 pin_message + unpin_message endpoint
- line 94 注释明确「401 / 403 / 422」三态校验
- line 95-99 401 检查 current_user
- line 100-103 svc.pin_message(PinMessageCommand) + current_user 参数
- **endpoint 层校验完整**
- **真正缺**：alembic 0012+0013 dual head race (merger migration 0014 未落)

#### 🚨 P1-2 Token 监控 — STATUS 写"持久化层未落"是**错的**

实际代码完整：
- `domain/usage/token_counter.py` 77 行（TokenCounter.count_user_message/count_completion + estimate_tokens CJK-aware + extract_completion_tokens）
- `domain/usage/usage_record.py` 44 行（UsageRecord dataclass + UsageWindow 1h/24h/7d + USAGE_KIND_*）
- `application/services/usage_service.py` 85 行（UsageService.record / record_completion / 用 UsageRepository + TokenCounter）
- `infrastructure/repositories/usage_repository.py` 148 行（PostgresUsageRepository.save + _to_domain + UsageRecordModel SQLAlchemy ORM）
- `api/routers/usage.py` 55 行（GET 3 endpoint: /usage, /usage/agents/{id}, /usage/sessions/{id}）

**5 层全在，STATUS 写的"持久化层未落"是错的**。真正缺的是：
- record_completion **在哪个调用点被触发**？（需要搜：orchestrator/LLM 响应后是否自动调 record_completion?）
- 缺 **integration test**（pytest 跑 0% 覆盖 usage.py / cli.py，httpx async test 没写）

**校正状态**：P1-2 = 完成 80%（5 层代码全在 + pytest 跑 service-level test 有，但 HTTP-layer + 触发点验证缺）

#### P1-3 CLI 扫描 — STATUS 描述基本对，但"调度器未集成"是核心

- `api/routers/cli.py` 完整（GET /api/cli/scan + 1h cache + DEFAULT_BINS + bins Query 参数 + refresh Query）
- `infrastructure/cli_scanner.py` 完整（scan_all(names) + ScanResult.to_dict() + 1h cache）
- `infrastructure/llm/cli_config_reader.py` 完整
- `infrastructure/llm/provider_scanner.py` 完整

**STATUS 写的"调度器未集成到 agent heartbeat loop"是真**：
- `grep -r scan_cli /api/cli/scan src/backend` 只在 4 处出现，全是 cli.py 自身 + test_cli_scanner.py
- 没有 startup event / heartbeat / cron 主动调用
- 端点只在被 HTTP 请求时执行

**校正状态**：P1-3 = 完成 70%（endpoint + cache + scanner 全在，缺 startup hook + 定期 cron + heartbeat 集成）

### 1d. 🚨 **真 bug 报告**: `deploy.py:81` FastAPI Annotated + Query(default) 冲突

**症状**:
```
from app.main import app
# AssertionError: `Query` default value cannot be set in `Annotated` for 'include_deleted'.
# Set the default value with `=` instead.
# File "src/backend/app/api/routers/deploy.py", line 81
```

**根因**: commit `f45a92f`（backend-p2 部署卡）引入 `include_deleted: Annotated[bool, Query(default=False)] = False` — FastAPI 0.10x+ 不允许在 `Annotated[..., Query()]` 里设 default 同时在 `=` 设 default

**修法**: 改 `Annotated[bool, Query()] = False`（参照 cli.py:28 正确写法）

**修复后验证**:
- `from app.main import app` → OK 60 routes
- `python -m pytest tests/ -q --no-cov` → **157 passed / 2 failed**（2 fail = test_pi_agent_e2e，本机无 pi binary 已知，per ADR-06 NB-02 defer）

**STATUS 写的"21/21 pytest 全绿"是 backend-p2 的子集**（不含 pi_agent E2E），实际 159 - 2 deferred = 157 真绿，1 - 2 deferred。

**STATUS 写的"168 pytest pass"是 plan_ba86c4d0 全部 backend task 累计**（spec + backend-p0-p1 + backend-p2 + ci），实际 157 + 一些 c2d2a59 落地后新加的 test ≈ 168，**差几个误差**。

## 2. Phase 2 阻塞（启服务 + Computer Use E2E）

**阻塞 1**: Docker Desktop 关闭（`docker ps` 报 "failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine"），无法启动 Postgres / Redis / 全栈

**阻塞 2**: backend `.env` 用 `postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub` — 强依赖 Postgres

**Phase 2 完整 E2E 没法做**（backend 起不来 = 前端 fetch 全 503/网络错）。但可以做：
- 启前端 dev server（不依赖后端）看 UI 渲染（mock data / loading state）
- 等 user 启 Docker Desktop 后再做完整 E2E

## 3. STATUS 校正（19:50 提交）

- P1-2 描述从"持久化层未落"改为"完成 80% + 缺触发点 + E2E test"
- P1-3 描述从"cli scan 端点全 work + 5 bin 1h cache" 改为"endpoint + cache + scanner 全在 + 缺 startup hook"
- 新增 deploy.py:81 bug 修复行（已修）

## 4. 关键教训

1. **STATUS 行号精确度不够** — 大致范围对，差 ±5-20 行。**不要根据 STATUS 的行号做精确定位**，先 `grep` 再 `Read`。
2. **plan_ba86c4d0 强收时 "21/21 pytest 全绿" 是 backend-p2 子集**，不含 pi_agent E2E（已 deferred）。**plan 累计 pytest = 157 pass + 2 deferred = 159**（接近 168 估计，含 c2d2a59 frontend test fixture + 一些新加的）。
3. **deploy.py FastAPI bug 真的存在** — 之前 owner 强收时 `from app.main import app` 这一步没跑（pytest 用 mock，没真启动 app），bug 漏过。**这是 owner override_accept 跳过 verifier 真实启动检查的代价**。
4. **Docker Desktop 关闭** — plan_ba86c4d0 跑期间就关了（之前 5/6 月部署用 Docker 起的，6/6 后改 local uvicorn），phase 2 真机 E2E 必须先开 Docker。

## 5. 给下一位的交接

- ✅ deploy.py:81 bug 已修（commit pending）
- ⚠️ Phase 2 启服务 + Computer Use E2E 待做（依赖 Docker Desktop 启动）
- M5/M6 手动补 3 gap 工作量重估：
  - P0-4 Pin session 校验 ~1h（migration + 2 测）
  - P1-2 Token 监控 ~30min（搜 record_completion 触发点 + 3 integration test，**不是 2h** — STATUS 估错了）
  - P1-3 CLI 扫描 ~1h（startup hook + 1 cron + 4 测）
  - 总计 **~2.5h**（不是 4h）
- Docker Desktop 起后跑 `docker compose -f src/docker/docker-compose.yml up -d` + `cd src/backend && uvicorn app.main:app --port 8000` + `cd src/frontend && npm run dev`
- Computer Use MCP 起 browser 走 `http://localhost:5174`
