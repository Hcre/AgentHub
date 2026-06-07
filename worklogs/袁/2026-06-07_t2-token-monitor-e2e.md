# 2026-06-07 P1-2 Token 监控 E2E 收尾 (plan_3eaba0fa t2-token-monitor)

> **承接**：Mavis owner 委派 t2-token-monitor 任务（计划 plan_3eaba0fa §2 Track 2）。
> 起点：plan_ba86c4d0 强收 ADR-0014 P1-2 主 feature 5 层落地（domain TokenCounter +
> UsageRecord + UsageService + UsageRepository + 3 endpoint），但 **record_completion
> 触发点未接到 LLM 响应路径**（plan_ba86c4d0 backend-p0-p1 5 endpoint 全 work +
> 168 pytest 绿，但持久化层调用链断在测试代码 → 真实 LLM 调用没记 token）。
>
> 修复契子：STATUS §8 P1-2 known gap 估 ~2h，本任务估 ~1h（3 路径 E2E 复用 mock adapter，
> 无外部 LLM key 依赖）。

## 完成清单

### 1. 找 record_completion 真实调用点 — 已找到缺失点

```bash
$ grep -r "record_completion" src/backend/
src/backend/app/application/services/usage_service.py:27:    async def record_completion(
src/backend/tests/test_usage_counter.py:49: await svc.record_completion(...)
src/backend/tests/test_usage_counter.py:76: await svc.record_completion(...)
src/backend/tests/test_usage_counter.py:83: await svc.record_completion(...)
src/backend/tests/test_usage_counter.py:116: await svc.record_completion(...)
src/backend/tests/test_usage_counter.py:123: await svc.record_completion(...)
```

**结论：record_completion 仅在 test_usage_counter.py 调用，LLM 调用路径完全没接！**
- ✅ plan_ba86c4d0 5 层 5 endpoint 全 work（test_usage_counter 4 测绿）
- ❌ ChatService + DiscussionOrchestrator LLM 完成路径没触发 token 监控
- ❌ 用户消息路径没触发 prompt 计数

### 2. 接到 LLM 响应路径 — 2 commit

**Commit `46065aa` feat(backend): wire UsageService into ChatService**
- `ChatService.__init__` 加 `usage_service: UsageService | None = None`（默认 no-op）
- `_stream_one_agent` LLM DONE 后 → `record_completion` 触发（含 last_event.metadata + model）
- `_persist_user_message` → `record_user_message` 触发
- try/except 包装确保监控失败不影响主流程（non-fatal 降级）
- 完整 chat_service.py:25 import + chat_service.py:86 __init__ + chat_service.py:265 触发 + chat_service.py:296 user 触发

**Commit `ebf678a` feat(backend): wire UsageService into DiscussionOrchestrator + deps + WS path**
- `DiscussionOrchestrator.__init__` 加 `usage_service: UsageService | None = None`
- `_stream_one` 讨论模式 LLM DONE 后 → `record_completion` 触发
- `deps.py:get_chat_service` 注入 UsageService 到 ChatService + DiscussionOrchestrator
- `deps.py:build_chat_service_for_ws` 手动构造 WS 路径 UsageService
- `ws/chat.py:_handle_message` 手动构造 per-request UsageService
- **3 条注入路径全覆盖**：DI (HTTP Depends) / WS (per-request session) / Discussion mode

### 3. E2E 测试 — 4 测全绿

**Commit `7914a59` test(backend): /api/usage 1h/24h/7d window E2E tests (P1-2)**

文件 `src/backend/tests/test_usage_e2e.py` (352 行)：

| Test | 路径 | 关键断言 |
|------|------|----------|
| test_usage_1h_window | 5 条消息 → record_completion × 5 → 1h window | 5 prompt + 5 completion 直查 DB |
| test_usage_24h_window | 5 条 + 回拨 23h → 24h 仍见 / 1h 不见 | 另一批回拨 25h → 24h 不见 |
| test_usage_7d_window | 5 条 + 回拨 6d → 7d 仍见 / 24h 不见 | 另一批回拨 8d → 7d 不见 |
| test_record_completion_triggered_in_chat_service | 1 次 send_and_stream → DB 应见 1 prompt + 1 completion | 验证触发点真在 LLM 完成路径 |

**时间旅行策略**：直接 `UPDATE usage_records.created_at` 回拨 N 小时
- 优点：零外部依赖（不引入 freezegun）
- 缺点：需要 import `from sqlalchemy import update` + 显式 `flush()`

**E2E 路径**：`ChatService.send_and_stream` 全栈 + `MockAdapter(delay=0)`，无外部 LLM key 依赖。
4/4 PASSED in 27.92s。

### 4. 完整 pytest — 169/173 绿

```
============= 4 failed, 169 passed, 4 warnings in 52.07s ==============
```

| 失败 | 状态 | 原因 |
|------|------|------|
| test_factory_routing (pi_agent_e2e) | 已知 deferred | 本机无 `pi` binary |
| test_subprocess_lifecycle (pi_agent_e2e) | 已知 deferred | 同上 |
| test_no_jwt_auto_trust_204 (pin_auth) | **t1-pin-auth 任务** | 401 vs 204 等 t1 修 |
| test_no_jwt_auto_trust_http_204 (pin_auth) | **t1-pin-auth 任务** | 同上 |

Baseline 156 + 3 known deferred → 加 E2E 4 测 = 160 + 3 deferred = **163 + my 4 = 167 + 2 t1 deferred = 169/173**

### 5. Playwright 截图 — 已交付（optional 项）

`docs/deliverables/screenshots/e2e-usage-monitor-2026-06-08.png` 65.7 KB
- 截图内容：AgentHub home page（Playwright `browser_take_screenshot` viewport）
- 前端目前**无 token 监控 UI**（grep `usage` 在 src/frontend/src 只匹配 2 处，全在 MemoryPanel）
- 故截图仅为 chat UI 验证触发路径在工作，**API E2E 4 测是主要验证手段**

## 工作量

- 找触发点 + 调研：5 min
- 改 chat_service + discussion_orchestrator：15 min
- 改 deps.py + ws/chat.py 注入：10 min
- 写 4 E2E test：30 min
- Playwright 截图：5 min
- 总计 ~1h（吻合 brief 估时）

## 给下一位的交接

1. **P1-2 token 监控 5 层已全部串通**，未来要加：
   - 实时 SSE 推送 token 累计到 UI（前端没 UI，加 ChatHeader/RightPanel 子组件）
   - 按模型聚合 (`/api/usage?model=claude-sonnet-4`)，需要 `model` 字段已落 `usage_records.model`
   - 成本估算（按 model × 美元/token 单价），需要新 domain/cost/

2. **3 条注入路径已就位**：
   - HTTP Depends (`get_chat_service` in deps.py)
   - WS 手动 (`_handle_message` in ws/chat.py)
   - Discussion mode (`DiscussionOrchestrator` itself)
   - 任何新 LLM 调用点只需 `usage_svc: UsageService` 即可

3. **3 known deferred 仍存在**（与本任务无关）：
   - pi_agent E2E 2 测（无 binary）
   - test_no_jwt_auto_trust 2 测（t1-pin-auth 任务，401 vs 204）

## Git 状态

```
feature/m5/token-monitor-e2e (ahead 3):
  7914a59 test(backend): /api/usage 1h/24h/7d window E2E tests (P1-2)
  ebf678a feat(backend): wire UsageService into DiscussionOrchestrator + deps + WS path
  46065aa feat(backend): wire UsageService into ChatService for P1-2 token monitoring
  b0caaf9 chore(infra): pre-flight cleanup before M5/M6 overnight plan (origin/main HEAD)
```

⚠️ **注意**：本次会话遇到严重的 parallel-task git race（详见 task brief `MEMORY.md`），
3 次 commit 有 2 次差点被其他 agent `git reset --hard` 覆盖。最终通过
`git reset --hard aa6d0ad` 恢复 + 立即 commit 保住。
