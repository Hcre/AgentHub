# AgentHub 测试策略

> 版本: v2.0 | 基于 PRD v4 M1-M6 + 架构设计 v1.0
> 目标覆盖率：后端 >= 80%，前端 >= 70%

---

## 一、测试金字塔

```
         ┌──────┐
         │ E2E  │  ~20 场景    Playwright        每 M 结束运行
         ├──────┤
         │ 集成  │  ~50 用例    pytest + httpx    每次 PR 运行
         ├──────┤
         │ 单元  │  ~150 用例   pytest + vitest   每次 commit 运行
         └──────┘
```

| 层 | 工具 | Mock 策略 |
|----|------|----------|
| **单元** | pytest (后端), vitest (前端) | Mock 所有外部依赖 |
| **集成** | pytest + testcontainers | 真实 PG + Redis，Mock LLM API |
| **E2E** | Playwright | Mock LLM API (录制 fixture)，其余真实 |

---

## 二、Mock 边界

| Mock（不需要真实服务）| 不 Mock（需要真实服务）|
|-----------------------|---------------------|
| Claude Code / Codex / TRAE → JSON fixture | PostgreSQL → Testcontainers |
| LLM API → fixture (正常/异常/流式/超时) | Redis → Testcontainers |
| GitHub Actions → Mock webhook | WebSocket → 真实连接 |
| Cloudflare Tunnel → Mock HTTP | Celery → 真实 broker | (v4: Celery 已移除，集成测试无需 broker)

---

## 三、单元测试

### 3.1 后端

| 模块 | 用例数 | 关键场景 |
|------|--------|---------|
| `task_engine.guard_transition()` | 12 | 合法转换/非法拒绝/预算超限/Worker未分配 |
| `task_engine.detect_cycle()` | 6 | 无环/单环/多环/空图/森林 |
| `task_engine.compile_to_canvas()` | 8 | 串行/并行/混合DAG |
| `task_engine.apply_event()` | 10 | 每种event_type折叠/幂等 |
| `coordinator.handle_agent_decision()` | 15 | 三种action/环拒绝/超限拒绝 |
| `mention_router.extract_mentions()` | 8 | 单@/多@/@All/无@/@协调者 |
| `dispatch_router.resolve()` | 8 | auto→协调者/auto→Agent/auto→检测/direct |
| `agent_service.create()` | 6 | 正常/name重复/agent_system非法/api_key加密 |
| `encryption.encrypt/decrypt` | 4 | 正常/错误密钥/空值 |
| `budget_controller.check()` | 6 | 四项全过/各单项超限/边界值 |

### 3.2 前端

| 组件 | 用例数 | 关键场景 |
|------|--------|---------|
| `StreamingText` | 5 | 空/逐字符/markdown/超长/特殊字符 |
| `MessageBubble` | 6 | user/agent/system/error/streaming/done |
| `AgentMention` | 4 | @弹出/过滤/选择/关闭 |
| `DiffCard` | 4 | 空/单文件/多文件tab/超大折叠 |
| `ApprovalCard` | 4 | approve/reject/edit/respond |
| `InboxView` | 5 | 全部/审批/任务/日历/空 |
| `AgentCreateForm` | 4 | 选系统→Model变化/填信息/提交/校验 |
| `chatStore` | 8 | 添加/更新/流式追加/删除/切换 |

---

## 四、集成测试

### 4.1 API

| 端点 | 用例数 | 关键场景 |
|------|--------|---------|
| `POST /api/agents` | 6 | Claude/Codex/Trae三种系统 / name重复 / api_key加密 |
| `GET /api/agents` | 3 | 全量/按system/按capability |
| `POST /api/groups` | 4 | 正常/空成员/协调者自动创建/协调者is_system |
| `POST /api/groups/{id}/members` | 3 | 添加/重复/不存在Agent |
| `POST /api/sessions` | 4 | 群聊/私聊/type校验/agent不存在 |
| `POST /api/sessions/{id}/messages` | 6 | auto→协调者/auto→Agent/auto→意图检测/direct |
| `POST /api/tasks` | 4 | 手动创建/assignee校验/嵌套>1拒绝 |
| `GET /api/tasks` | 5 | 组合筛选/排序/分页/空结果 |
| `POST /api/approvals/{id}/approve` | 4 | approve/reject/edit/respond |
| `GET /api/inbox` | 4 | 分类/未读/分页/空 |

### 4.2 数据库

| 测试 | 关键场景 |
|------|---------|
| Migration | 全部正向apply + 全部反向rollback |
| 事件溯源 | 正常重建/空事件/幂等键去重 |
| 并发任务领取 | SKIP LOCKED 两个Worker不同时领同一任务 |

### 4.3 WebSocket

| 测试 | 关键场景 |
|------|---------|
| 连接认证 | 有效token/无效/过期 |
| 消息收发 | 单发单收/广播/离线重连增量 |
| 流式推送 | 逐token/中断重连 |
| 心跳 | 正常/超时断开 |

---

## 五、E2E（Playwright，覆盖 5 个 Core User Stories）

| # | Story | 场景 | M |
|---|-------|------|----|
| E2E-01 | S1 单聊 | 创建Agent→私聊→发消息→流式回复→代码块 | M2 |
| E2E-02 | S2 群聊 | 创建群组→添加Agent→发任务→协调者分解→多Agent并行→结果合并 | M3 |
| E2E-03 | S3 预览 | Agent返回代码→Diff卡片绿红标注→iframe预览→修改→确认 | M4 |
| E2E-04 | S4 上下文 | 群聊任务→Harness注入GlobalContext→Worker引用共享制品 | M3 |
| E2E-05 | S5 创建Agent | 选Claude→配DeepSeek模型→填api_key→Agent出现→可调度 | M4 |
| E2E-06 | 审批 | Agent请求删文件→收件箱Badge→APPROVE→继续执行 | M4 |
| E2E-07 | 断线重连 | 断网10s→恢复→消息同步 | M5 |
| E2E-08 | 超长会话 | 200+条→自动压缩→早期消息可查 | M5 |

---

## 六、每里程碑验收门禁

| M | 单元通过 | 集成通过 | E2E |
|----|---------|---------|-----|
| M1 | >= 30 | >= 5 | - |
| M2 | >= 60 | >= 15 | E2E-01 |
| M3 | >= 100 | >= 30 | E2E-01~04 |
| M4 | >= 130 | >= 45 | E2E-01~06 |
| M5 | 全部 | 全部 | 全部 8 个 |

---

## 七、手动验证

| # | 场景 | 方式 | M |
|---|------|------|----|
| V1 | Claude/Codex/TRAE 真实调用 | 真实 API Key | M1 |
| V2 | 自定义 base_url 接入 DeepSeek/GLM | 真实 API Key | M1 |
| V3 | PWA 安装到手机 | 真机 | M5 |
| V4 | 10 并发压力测试 | locust | M5 |
