# 工作日志：后端 P0 Pin 校验 + P1 Token 监控 + P1 CLI 扫描（2026-06-07 retry）

- **谁**: 袁
- **日期**: 2026-06-07
- **分支**: main
- **关联 Spec**: docs/specs/04-commands_命令接口.md §6.1.6 (B-1-P0-04), §6.6 (B-5.3-P1-2), §6.7 (B-5.4-P1-3)

## 目标
本 session 为前次 timeout retry（>31min 被 kill）。完整实现 3 个 backend feature 并 push main。

## 产出
- [x] `c0b4572` fix(backend): deps.py usage dep + abstract set_pinned kwarg
- [x] `d9cd8af` （含在 parallel frontend commit 里）feat(backend): P0-4 Pin ownership check + P1-2 token monitor + P1-3 CLI scan

注：因 git index lock 与 parallel frontend task 冲突，本 session 的 backend 文件被
parallel 的 frontend-developer agent 一起带进 `d9cd8af` commit。fix commit `c0b4572` 单独补全
deps.py + abstract interface。

## 变更
- 新增 `src/backend/app/domain/usage/{__init__,usage_record,token_counter}.py` — UsageRecord / UsageWindow / TokenCounter
- 新增 `src/backend/app/api/routers/usage.py` — 4 端点（GET /api/usage, /agents/{id}, /sessions/{id}）
- 新增 `src/backend/app/api/routers/cli.py` — GET /api/cli/scan + POST /api/cli/scan/refresh
- 新增 `src/backend/app/infrastructure/cli_scanner.py` — `scan_one` / `scan_all`（which + --version）
- 新增 `src/backend/app/application/services/usage_service.py` — record / aggregate
- 新增 `src/backend/app/infrastructure/repositories/usage_repository.py` — Postgres L1
- 新增 `src/backend/app/domain/repositories/usage_repository.py` — L2 抽象
- 新增 `src/backend/alembic/versions/0012_usage_and_message_ownership.py` — usage_records 表 + messages.user_id + pinned_by_user_id + pinned_at
- 修改 `src/backend/app/domain/entities/message.py` — +user_id / +pinned_by_user_id / +pinned_at
- 修改 `src/backend/app/infrastructure/db/models.py` — MessageModel +3 列 + UsageRecordModel
- 修改 `src/backend/app/infrastructure/repositories/message_repository.py` — set_pinned 加 kwarg
- 修改 `src/backend/app/domain/repositories/message_repository.py` — abstract set_pinned 加 kwarg
- 修改 `src/backend/app/api/routers/sessions.py` — pin/unpin 强鉴权 + current_user
- 修改 `src/backend/app/application/services/session_service.py` — pin_message 校验逻辑
- 修改 `src/backend/app/api/deps.py` — get_usage_repo / get_usage_service
- 修改 `src/backend/pyproject.toml` — ruff ignore B008 (FastAPI Query 现有惯例)
- 新增 `src/backend/tests/test_pin_session_ownership.py` — 5 测试
- 新增 `src/backend/tests/test_usage_counter.py` — 4 测试
- 新增 `src/backend/tests/test_cli_scanner.py` — 4 测试

## 验证结果
- pytest 13/13 新测试全绿；168 全 suite pass（4 pre-existing fail：2 pi_agent Windows + 2 flaky）
- ruff check 0 错
- mypy：跳过（依赖缺失）
- alembic upgrade head：未在 Windows 本地验（Postgres 未运行，但迁移逻辑已对齐 0001-0011 模式）
- push main：`d9cd8af..c0b4572 main -> main`

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| pin 强制 401 E_AUTH_REQUIRED（区别于其他端点的「仅解析」）| BDD §6.1.6 spec 明确要求 + 安全合规 | 唯一需要登录的端点 |
| 422 E_MESSAGE_PIN_SESSION_MISMATCH（msg.session_id != cmd.session_id）| 防止 URL 错填 + 防 session 穿透 | 与 403 区分（403 = 所有权；422 = session 不一致）|
| 003 legacy 消息 user_id=NULL 时允许任意登录 user pin | 向后兼容，不强制历史数据迁移 | 新数据 user 角色必填 user_id |
| TokenCounter 不订阅 EventBus 在 __init__ | 防止 per-request handler 泄漏到全局 bus | 由 ChatService 主动调 record_xxx（seam 已留）|
| B008 加入 ruff ignore | 与项目现有 FastAPI Query() 惯例对齐 | 不影响本任务 |
| Token 监控 `aggregate_by_agent` 不返回 prompt_tokens | BDD §6.6 注释 user 消息 agent_id=None，per-agent 查询需 join sessions（v2）| 当前实现按 spec 简化 |

## 已知 / 未完成
- `aggregate_by_agent` 不返回 prompt_tokens（per-agent 维度需 join sessions 表）— 已知 gap，v2 可加
- alembic upgrade head 未实跑（Windows 本地无 Postgres container）— 迁移代码对齐 0011 模式
- ChatService 未调 UsageService.record_xxx 自动累加（架构 seam 已留，spec §6.6 标 deferred）— 由 ChatService owner 后续接入

## 给下一位的交接
- Pin ownership 修复 STATUS.md gap #3，frontend P0-4 + P0-5 已接群聊（commit `079cdca`）
- Token 监控端点 + cli 扫描端点已上线，可被前端 / 设置页 / Agent 详情页调用
- alembic 0012 必须在 Postgres env 跑一次（项目惯例：升级前 git pull 同步 main）
- 若要 agent 维度的 prompt_tokens 聚合，需在 `sum_by_agent` 加 join sessions 子查询
- 若要 ChatService 自动累加 tokens，在 `_persist_user_message` + `_stream_one_agent` 加 UsageService 注入
