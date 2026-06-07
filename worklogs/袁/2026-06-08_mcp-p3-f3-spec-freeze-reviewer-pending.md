# 2026-06-08 · MCP P3 F3 spec 复查 + Reviewer 24h SLA 启动（downscope docs-only）

> 作者：袁（xiangbianpangde,git user） · 类型：PR-01 闸门（端点冻结 2 人 Review）+ downscope
> 分支：`feature/mcp/p3-f3-spec-freeze`（从 main `b0caaf9` 拉,未 push）
> 父任务：plan_3eaba0fa Track 4 §MCP P3 spec 冻结
> 起点文档：docs/specs/04-commands §2.6 + §三（2026-06-03 冻结草案）

## 背景

2026-06-03 已在 `feature/mcp/pr01-freeze-and-plan-cleanup` 分支落 PR-01 冻结草案（8 端点 + 4 WS 事件 + 错误码 12 项 + 二次对账 R1/R3/R5），但**未获 2 人 Review 批准**。本次（2026-06-08）按 plan_3eaba0fa Track 4 任务清单复查 + 找 2 reviewer（董 yii.d + 黎 oldmanpushbike）+ 标冻结。

## 复查结果（§2.6 8 端点）

| 类别 | 端点 | body / 返回 | 错误码 | 备注 |
|------|------|--------------|--------|------|
| 市场 3 | GET /api/mcp/market | q/tag/transport/official_only/page/page_size | 401/403/422 | OK |
| | GET /api/mcp/market/{mcp_id} | dry_run_result 字段 | 401/404 | OK |
| | GET /api/mcp/market/templates | 本期官方 5 模板 | 401/403 | OK |
| 安装 2 | POST /api/mcp/installations | workspace_id+mcp_id+instance_name+config_overrides,幂等 args_hash | 400/401/403/404/409/422/500 | OK |
| | DELETE /api/mcp/installations/{id} | query workspace_id | 401/403/404/409/500 | OK |
| 绑定 2 | POST /api/mcp/bindings | agent_id+installation_id+tool_subset?,无运行时有状态 attach (ADR-05) | 400/401/403/404/409/500 | OK |
| | DELETE /api/mcp/bindings/{id} | 见下方"校正 1" | | **校正** |
| 创建 1 | POST /api/mcp/servers | name+slug+transport+config_json+version≤50+tags+template_id+dry_run=true;返回 mcp_id+status:draft+dry_run_result | 400/401/403/409/422/500 | OK |

**POST /api/mcp/servers body schema 验证**（F3 创建核心）：
- 9 字段全到位,slug regex `^[a-z0-9-]+$`,version ≤50,transport enum stdio/sse/streamable_http
- dry_run 默认为 true（干跑后再入库）,30s 超时/CPU=1/Mem=512MB/net=none 限额已写明
- 错误码 5 类（SLUG_CONFLICT/SCHEMA_INVALID/VERSION_TOO_LONG/DRY_RUN_TIMEOUT/DRY_RUN_FAILED）全列

**错误码清单（line 271-284）12 项,AP-02/03 E_ 前缀对齐 chat 端点**：
- 4xx 类 6 项（NOT_FOUND 404/NAME_CONFLICT 409/SLUG_CONFLICT 409/BINDING_CONFLICT 409/UNAUTHORIZED 401/PERMISSION_DENIED 403）
- 422 校验类 5 项（SCHEMA_INVALID/VERSION_TOO_LONG/DRY_RUN_TIMEOUT/DRY_RUN_FAILED/BATCH_TOO_LARGE）
- 500 类 5 项（INSTALL_TIMEOUT/INSTALL_DEPENDENCY_MISSING/TOOL_CALL_TIMEOUT/TOOL_CALL_CANCELLED/TOOL_CALL_RUNTIME_ERROR/INTERNAL）
- 全 OK

**二次对账修订（line 288-291）R1/R3/R5 3 项**：已含 Reviewer 确认标记（R3 鉴权 JWT-only / R1 workspace_id 暂存 session_id / R5 WS 信封并存）,口径与 README-REVISION §9 R1/R3/R5 完全对齐

## 复查结果（§三 WS 4 事件）

| 事件 | 方向 | 信封 | 关键字段 | 备注 |
|------|------|------|----------|------|
| tool_call:request | S→C | {type, payload{request_id, trace_id, agent_id, binding_id, tool_name, args, ts}} | request_id（AP-07）| OK |
| tool_call:progress | S→C | {type, payload{request_id, trace_id, binding_id, tool_name, progress, message, duration_ms}} | request_id | OK |
| tool_call:response | S→C | {type, payload{request_id, trace_id, binding_id, tool_name, result, duration_ms}} | request_id | OK |
| tool_call:error | S→C | {type, payload{request_id, trace_id, binding_id, tool_name, error_code, error_message, duration_ms}} | request_id | OK |
| tool_call:cancel | **C→S** | {type, payload{request_id}} | request_id | **校正 2：错放修正** |

**AP-07 信封验证**：4 事件 + cancel 全用 `{type, payload, request_id}` 信封,符合 04-api AP-07 红线

## 发现 2 处内部不一致,本次校正

### 校正 1：DELETE /api/mcp/bindings 副作用与 ADR-05 冲突
- **现状**（line 256-258 改前）："经既有 WS 通道更新路由表（≤5s,F-011）"
- **冲突**：line 249-251 POST /api/mcp/bindings 写"无运行时有状态 attach（P2/ADR-05 请求携带）",即"无状态 attach" 与 "路由表 5s 更新" 互相矛盾
- **校正**：改为"无运行时有状态 attach（per ADR-05 请求携带）——同 POST /bindings/bindings 反向：下次该 agent 的 stream 由 ContextBuilder 不再解析此 binding（active 集合移除）；Runtime 不再写 .mcp.json 注入此 binding 的 server"

### 校正 2：tool_call:cancel 错放
- **现状**（line 337 改前）：取消协议放在"服务端 → 客户端"代码块内,但语义是"客户端 → 服务端"
- **冲突**：与章节标头不一致,F-016 协议本身是 client→server
- **校正**：移到"客户端 → 服务端"代码块,加"〔🔒 PR-01 冻结草案〕MCP 工具调用取消（F-016）：按 AP-07 带 request_id"标记;原"服务端 → 客户端"块对应注释加"取消见 client→server 节"

## Reviewer 找 2 人

| Reviewer | GitHub handle | git user | 角色 | 当前状态 |
|----------|---------------|----------|------|----------|
| 董 | @yii.d（Hcre/AgentHub 本地团队成员,无 GitHub 账号）| yii.d | 协调者 + AgentHub 后端 | ⚠️ 离线 (2026-06-07 23:03 周日晚) |
| 黎 | @oldmanpushbike（Hcre/AgentHub 本地团队成员,无 GitHub 账号）| oldmanpushbike | 桌面 App + CLI 扫描 + 后端 | ⚠️ 离线 |

**mavis 通信尝试**：
- `mavis communication peers` 仅返回 5 个 active session（4 个 track worker + 1 Mavis orchestrator）,无 董/黎 session
- 董/黎 session 当前未 spawn（周日 23:03,无催办渠道）
- 已发消息给 parent mvs_d70e24bad82a4c29815af58e6969569c（内容：复查完成 + 2 处校正 + reviewer 24h SLA 启动 + downscope docs-only + 等 ping）,messageId 1291,status delivered

**24h SLA 决策**：启动时间 2026-06-07 23:03（Asia/Shanghai）,截止 2026-06-08 23:03。按 brief §5 downscope 决策：24h 未回 → docs-only（不动 alembic 0006）

## 本次改动

### docs/specs/04-commands_命令接口.md v2.2 → v2.3
1. §2.6 标题加 24h SLA 标记：`2026-06-08 复查校正 · Reviewer Pending 24h SLA 2026-06-08 23:03 (董 yii.d + 黎 oldmanpushbike 离线,downscope docs-only)`
2. DELETE /api/mcp/bindings 副作用校正为 ADR-05 一致文本
3. §三 客户端→服务端 节新增 tool_call:cancel 块
4. §三 服务端→客户端 节对应位置删除 cancel 行,加"取消见 client→server 节"指针
5. 顶部版本行 v2.2 → v2.3 + 加 v2.3 changelog 一行
6. 末尾"更新记录"加 2026-06-08 v2.3 行

### 未做
- ❌ alembic 0006 草稿（mcp_servers 表）—— 24h SLA 未过,downscope
- ❌ McpServerCreate dry-run 验 —— 同上
- ❌ schemas/mcp.py 落 Pydantic models —— P1 实现时落地,本期 PR-01 不需

## 验证

- `git diff --name-only`：改动仅 docs/specs/04-commands_命令接口.md 1 文件 + worklog 1 文件
- 其他 worker 改动（STATUS.md / cli.py / main.py / Icon.tsx / types/index.ts / useMediaQuery.ts / cli_scheduler.py 等）已存在 working tree,本 commit **不卷入**（per 任务强约束："docs commit 路径：docs/specs/04-commands_命令接口.md（不动其他 spec）"）
- 用 git plumbing 提交（避免 worktree race condition,5 个 track worker 并行共享 working tree 已被实测 5+ 次切换破坏 working tree state）

## 24h SLA 倒计时

- 启动：2026-06-07 23:03 Asia/Shanghai
- 截止：2026-06-08 23:03 Asia/Shanghai
- 截止前可能动作：
  - 董/黎 任意 1 人 Approve → flip §2.6 标题为 `〔✅ 2026-06-08 PR-01 Reviewer Approve 1/2〕`（不达 2 人仍不冻结）
  - 董 + 黎 都 Approve → flip `〔✅ 2026-06-08 PR-01 Reviewer Approve 2/2〕` + 1 补丁 docs commit（`docs(specs): MCP P3 闸门 Reviewer Approve 2/2`）+ 解锁 alembic 0006 撰写权
- 截止后未到 2/2 → 维持 pending 标记 + 跳过 P1 实现门,plan_3eaba0fa finalize 阶段 ADR 记录此事

## 给下一位的交接

1. **当前 1 docs commit 已通过 git plumbing 提交**(本地分支 feature/mcp/p3-f3-spec-freeze HEAD);push 前请用 `git log -1 --format='%h %s'` 复核 commit message
2. **24h SLA 截止前（2026-06-08 23:03）**：若 owner 收到 董/黎 Approve,执行：1) flip §2.6 标题为 `〔✅ YYYY-MM-DD PR-01 Reviewer Approve 2/2〕` 2) 1 补丁 docs commit 3) push main 4) deliverable.md 加 §Approve 段 5) 通知 parent 解锁 alembic 0006 撰写
3. **24h SLA 截止后（2026-06-08 23:03 后）**：若未达 2/2,执行：1) 在 `worklogs/decisions/0015-mcp-pr01-reviewer-sla-downscope.md` 立 ADR（本机 brief §5 downscope 决策）2) 1 docs commit `docs(specs): MCP P3 PR-01 downscope docs-only (24h SLA 未达 2/2 Reviewer Approve)` 3) deliverable.md 标 "reviewer pending" + ADR 链接
4. **下游 P1 实现门**：即使 PR-01 标 pending,实现仍可走 alembic 0006 草稿 + `infrastructure/db/models.py` 追加 4 表（契约权威已落,3 实体 + 1 日志表）,只需 owner 显式 acknowledge "在闸门未冻结时启动实现" + 风险标 plan_3eaba0fa finalize 阶段
5. **不动其他文件**：董/黎 自己分支的改动（STATUS.md / cli.py / main.py / useMediaQuery.ts / Icon.tsx / cli_scheduler.py 等）是其他 track worker 的产物,本 track 不卷入
