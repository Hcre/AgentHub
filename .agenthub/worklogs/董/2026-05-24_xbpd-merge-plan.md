# xbpd 前端合并方案 v3

> 日期：2026-05-24 | v3：基于逐文件代码核对修正（行号即证据）| 验收标准：真实 LLM 对话
>
> v2→v3 改动：①验收改两段式（先 anthropic_api 直连，后 claude_code+proxy）②容器无 CLI 阻塞点显式化 ③provider 补 deepseek 从「低优先」升为 §四 必改 ④新建 agent 默认 offline 映射处理 ⑤§十执行起点校正（当前工作树是编译失败半成品）⑥§五补 addUserMessage ⑦新增 §十四 后端死注入链清理（解耦项）

## 一、数据模型裁决

xbpd 采用 **keyed 多会话模型**，是正确方向，保留不动。

| 维度 | xbpd 模型（采用） | main 旧模型（废弃） |
|------|-------------------|---------------------|
| 消息存储 | `Record<convKey, ChatMessage[]>` 按 agentId:convId 分桶（`chatStore.ts:36`） | `ChatMessage[]` 扁平数组 |
| 消息格式 | `{id, from, text, time}`（`types/index.ts:61`） | `{id, role, content, streaming?}` |
| 会话概念 | 内置：Conversation[] + convKey | 外部：单一 sessionId |

承认：main 的 `useWebSocket.ts` 是为旧模型写的，直接恢复无法使用。需要重写。

## 二、可复用与不可复用

**可直接复用（3 个）**：
- `api/client.ts` — fetch 封装，模型无关
- `api/agents.ts` — 但 `import type { Agent }`（`agents.ts:2`）需改为 `ApiAgent`（见 §三）；CreateAgentInput 需扩字段（见 §四）
- `api/sessions.ts` — 端点与后端一致（`POST /api/sessions {type,agent_id,title}` 对得上 `routers/sessions.py:29`）

**不可复用，需重写（1 个）**：
- `hooks/useWebSocket.ts` — 当前是**改了一半的单会话版**（已 import StreamEvent，但 `applyStreamEvent(event)` 无 key，且调的 store 方法不存在）。与 xbpd 的 keyed 多会话不兼容，需重写。

## 三、类型冲突解决

问题：xbpd 的 `Agent`（UI 用途，有 color/online，`types:35`）与后端 `AgentOut`（API 用途，有 provider/model/skills，`schemas/agent.py:41`）形状不同。当前 `agents.ts:16` `api.get<Agent[]>` 把 UI 类型当后端 DTO，**类型错误**。

解决：
1. xbpd 的 `Agent` 保持原名不动（UI 组件全用它）
2. 新增 `ApiAgent` 类型，对应后端 `AgentOut` 的字段
3. `api/agents.ts` 的 `import type { Agent }` 改为 `import type { ApiAgent }`
4. agentStore 内部维护 `ApiAgent → Agent` 映射：
   - `color`：按 `ApiAgent` 列表索引轮转分配（brand/sage/clay/rose/blue/neutral）
   - `online`：`status === "online"`（后端枚举 online/offline/busy/error）
   - `skillCount`：`skills.length`
5. 新增 `streaming?: boolean` 到 ChatMessage（支持流式增量渲染）
6. 追加 `StreamEvent`、`StreamEventType`、`Session` 类型（纯增量，不冲突）

⚠️ **新建 agent 默认 offline**（`entities/agent.py:37` `status = AgentStatus.OFFLINE`）。若直接套 `online = status==="online"`，刚创建的 agent 会显示离线。处置二选一：
- 前端：`createAgent` 本地映射时对新建项乐观置 `online: true`；
- 后端：创建时置 `ONLINE`（更正，但属后端改动，需董确认）。
- 本方案默认走前端乐观置 online，不动后端。

## 四、agent_system 两级模型（真实对话关键）⭐

**问题**：后端 `build_adapter_for_agent` 按 **`agent_system`** 选适配器（`factory.py:19`，且 `chat_service.py:98` 在流式路径确实调用它）。xbpd 表单只收 `provider`，从不发 `agent_system` → 后端 `AgentCreateRequest` 默认 `AgentSystem.MOCK`（`schemas/agent.py:17`）→ 对话全是假数据。且 proxy 强制要 `base_url`（`handler.py:55`，无则 `400`）和 `api_key`（`handler.py:50`，无则 `400`），表单也不收 base_url。

**设计**：表单暴露「运行时」+「接入模型」两层（正交，非冗余）。

| 层 | 字段 | 取值 |
|----|------|------|
| ① 运行时 | `agent_system` | `claude_code` / `anthropic_api`（首推验收）/ `mock` |
| ② 接入模型 | `provider` + `model` + `base_url` + `api_key` | 经 proxy 透传到任意 Anthropic 兼容端点 |

**各运行时所需字段**：
- `anthropic_api`：`model` + `api_key`（直连 ClaudeAdapter，**无需 base_url、无需 CLI、无需 proxy**，`factory.py:21`）→ **首次验收首选**
- `claude_code`：`model`(→ANTHROPIC_MODEL) + `base_url`(必填，如 `https://api.deepseek.com/anthropic`) + `api_key`(必填) → 依赖宿主机装 Claude CLI（见 §十一/§十三）
- `mock`：无（演示用）

**能力边界（写进 UI 提示）**：
- proxy 当前**纯透传，只换 `x-api-key` header，不转协议**（`handler.py:69` 实测）。
- ∴「任意模型」= 提供 **Anthropic 兼容端点**的：DeepSeek `/anthropic`、Kimi、GLM、Anthropic 官方。
- **纯 OpenAI 格式（GPT/Qwen）暂不可用**——需协议转换层，董标为后续扩展。
- `OPENAI_API` 直连分支也是 `return MockAdapter()`（未实现，`factory.py:30`）→ UI 暂隐藏或标灰。
- ⚠️ proxy 模式下 `provider` 字段**仅是元数据标签，不参与转发路由**（转发只看 `base_url`+`api_key`）。填表人需明白：决定打到哪的是 `base_url`，不是 `provider`。

**CreateAgentModal 改动**：
- 加「运行时」下拉（agent_system），首次验收期默认 `anthropic_api`，稳定后切 `claude_code`
- claude_code 运行时下显示 `base_url` 输入（可按 provider 预设填充 DeepSeek 等）
- 提交时合成 `avatar`（首字母/emoji，后端 `schemas/agent.py:14` 必填）
- ⭐ **provider 下拉补 `deepseek` 选项**（`data/extra.ts:14` 当前只有 anthropic/openai/azure；后端 `enums.py:18` 枚举已含 deepseek）。否则 §四 推荐的 claude_code+DeepSeek 路径选不出 provider。**此项为必改，非低优先**。

## 五、chatStore 桥接

原则：**ChatView 要改，但要改得少**。接受审查结论——「组件不动」与「真实通信」不可兼得。

ChatView 最小改动：
1. 新增 `useWebSocket(sessionId)` 调用（在 store 拿到 sessionId 后）
2. 将 Composer 的 `onSend` 从 `chatStore.send()` 改为 `ws.sendMessage()`
3. 监听 `StreamEvent` 后调用 `chatStore.applyStreamEvent(key, event)`

chatStore 改动：
1. 新增 `sessionIds: Record<string, string>` — convKey → sessionId 映射
2. 新增 `connected: boolean` + `setConnected`
3. 新增 `addUserMessage(key, text)` — useWebSocket 发送时本地回显用户气泡（`useWebSocket.ts:64` 已在调它）
4. 新增 `applyStreamEvent(key, event)` — 对 key 对应桶做流式增量：text 事件追加到 `__streaming__` 哨兵消息，done 事件替换哨兵为最终消息（用 `messageOutToChatMessage` 转 role→from / content→text / time）
5. `send()` 保留本地消息添加 + typing 逻辑，但删除 `setTimeout` 假回复；实际发送由 ChatView 通过 WebSocket 完成

mock 降级：WebSocket 未连接时，send() 回退到 setTimeout 假回复。

## 六、agentStore + CreateAgentModal 桥接

1. 初始值从 `seedAgents`（`agentStore.ts:35`）改为空数组
2. 新增 `loadAgents()` — 调 `agentsApi.list()`，`ApiAgent → Agent` 映射后写入
3. `createAgent()` — 本地添加 + `agentsApi.create()` 同步后端。**边界转换**：
   - 命名：`apiKey → api_key`、`systemPrompt → system_prompt`（agentStore 用 camelCase，api 层用 snake_case，是两个不同的 CreateAgentInput）
   - 新增字段：`agent_system`、`base_url`、合成 `avatar`
   - 密钥红线：`api_key` 仅传后端加密存储，前端 store 不留明文（`agentStore.ts:50` 已遵守）
4. `removeAgent()` — 本地删除 + `agentsApi.remove()` 同步后端

## 七、不改的部分

- taskStore / groupStore / inboxStore — 保持 mock（后端 API 仅有 GET 列表空壳，无数据可接）
- 所有 UI 组件（ChatView、CreateAgentModal 除外）
- 配置文件、原型、样式、lib/
- data/mock.ts 和 data/groups.ts — 保留作为初始种子/降级

## 八、ChatView 改动清单

| 改动 | 说明 |
|------|------|
| 新增 `import { useWebSocket }` | 重写后的 key-aware WS hook |
| 新增 `import { sessionsApi }` | 获取真实 sessionId |
| 新增 `useEffect` 创建 Session | 首次渲染时调 `sessionsApi.createPrivate(agent.id)` 拿 sessionId，写入 chatStore.sessionIds |
| 新增 `useWebSocket(sessionId, convKey)` | WS 连接 + 事件路由到对应会话桶 |
| `onSend` 改为 `sendMessage` | Composer 的回调从 chatStore.send 改为 useWebSocket 的 sendMessage |
| `ws.onmessage` 回调 | 解析 StreamEvent → chatStore.applyStreamEvent(key, event) |

## 九、契约差异速查（修改依据）

| # | 差异 | 修改位置 |
|---|------|---------|
| 1 ⭐ | `agent_system` 缺失 → 默认 mock（`schemas/agent.py:17`） | §四：表单加运行时下拉 |
| 2 ⭐ | proxy 必填 `base_url`+`api_key`（`handler.py:50/55`） | §四：claude_code 下显示 base_url |
| 3 | `avatar` 后端必填（`schemas/agent.py:14`），xbpd 不收 | §六：提交时合成 |
| 4 | 命名 camelCase↔snake_case | §六：agentStore→api 边界转换 |
| 5 | `ChatMessage` 形状不一致 | §五：messageOutToChatMessage 适配器 |
| 6 | `Agent` 形状不一致 | §三：ApiAgent + 映射 |
| 7 ⭐ | provider 下拉无 `deepseek`，与 §四 推荐路径冲突 | **§四 必改**（已从 v2「低优先」升级） |
| 8 | 新建 agent 默认 offline（`entities/agent.py:37`） | §三：前端乐观置 online |
| 9 (minor) | WS 多发 `type` 字段 | 后端 `chat.py:44` 读 `type=="message"`，对得上，无需改 |

**契约对得上（仅追加类型，无需改后端）**：StreamEvent 8 种类型（`protocol.py:34-42`）前后端一致；WS 发送 `{type:"message",content}` 后端可读（`chat.py:44/54`）；sessions 端点 / proxy_base_url 均就绪。

## 十、执行顺序

> ⚠️ **起点校正**：当前工作树 **不是干净的 xbpd**。4 个 `api/*` + `useWebSocket.ts` 已被 `git add`，但 `types/index.ts` 仍是纯 xbpd 原版（无 Session/StreamEvent/ApiAgent），chatStore 无 applyStreamEvent/setConnected/addUserMessage。**`tsc` 当前必然失败**（`sessions.ts:2` import 不存在的 Session；`useWebSocket.ts:13-15` 调不存在的 store 方法）。执行第 1 步是「校正这批半成品」，不是「删 main 原版」。

| # | 操作 | 文件 |
|---|------|------|
| 0 | `cd frontend && npm install`（解锁 tsc，否则所有 import 报错被掩盖） | — |
| 1 | 校正现有半成品：删除当前单会话版 `useWebSocket.ts`（将于第 4 步重写） | 1 |
| 2 | 新增 `ApiAgent` + `StreamEvent`/`Session`/`StreamEventType` + `streaming` 字段 | types/index.ts |
| 3 | 改 `api/agents.ts`（Agent→ApiAgent；CreateAgentInput 加 agent_system/base_url） | 1 |
| 4 | 重写 `useWebSocket.ts`（key-aware） | 1 |
| 5 | 修改 chatStore（applyStreamEvent + sessionIds + connected + addUserMessage + send 改造 + 适配器） | 1 |
| 6 | 修改 agentStore（loadAgents + API 桥接 + 命名/字段转换 + 新建乐观 online） | 1 |
| 7 | 修改 CreateAgentModal（运行时下拉 + base_url + avatar 合成 + provider 补 deepseek） | 1 |
| 8 | 修改 ChatView（WS + Session 创建） | 1 |
| 9 | `npx tsc -b` 零错误（门禁） | — |
| 10 | 启动全链路验证（见 §十一） | — |
| 11 | 合并到 yii.d（见 §十二） | — |

## 十一、验收标准（真实 LLM，两段式）

> 设计原则：先用依赖最少的路径证明「前后端真实链路通」，再验证依赖最重的 claude_code。

**段 A — anthropic_api 直连（首验，依赖最少）**
只需一个 Anthropic api_key，无 CLI、无 proxy、无 base_url。
```bash
cd backend && uvicorn app.main:app   # 裸跑，不必容器
cd frontend && npm install && npm run dev
# 1. tsc -b 零错误
# 2. 创建 Agent：运行时选 anthropic_api，填 model + api_key
#    → POST /api/agents 201，DB 落 agent_system=anthropic_api
# 3. 私聊 → POST /api/sessions 201 → WS /ws/sessions/{id} 连接
# 4. 发消息 → 收到真实 StreamEvent text 流 → 气泡增量渲染 → done 收尾
# 5. 断开后端 → mock 降级不崩
```

**段 B — claude_code + proxy（次验，依赖最重）**
```bash
# 前置（阻塞）：claude_code 走 CLI 子进程（claude_code_runtime.py:102/149 起 "claude"）。
#   后端 Dockerfile 当前不装 node/claude → 容器内 claude_code 必 FileNotFoundError。
#   ∴ 段 B 二选一：① 宿主机裸跑后端（已装 claude CLI）；② 改 Dockerfile 加装 node+claude 再 docker compose up。
# 1. 先用 manual_test_claude.py 确认后端 claude_code + proxy 单独跑通
# 2. 创建 Agent：运行时选 claude_code，provider 选 deepseek，
#    填 model + base_url(https://api.deepseek.com/anthropic) + api_key
# 3. 同段 A 步骤 3-4，验证真实流式
# 4. base_url 填错 → proxy 400 → 前端有可读报错
```

**段 C — 回归**：tasks/groups/inbox 页面 mock 正常渲染（不报错）。

## 十二、yii.d 合并范围确认

`xbpd..yii.d` 为空，yii.d 是 xbpd/main 的祖先 → 可 `--ff-only`，零冲突。

```bash
git checkout yii.d
git merge --ff-only feature/domain2/frontend-integration
# yii.d 从此 = main + 新前端集成
```

合并到 yii.d 的实际效果是 yii.d 快进到全量——既含前端重建，也含已合入 main 的后端代码（CLI proxy 等）。这是预期行为：yii.d 作为个人集成分支，理应包含所有已验证改动。

## 十三、风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| **容器无 claude CLI**：Dockerfile 不装 node/claude，容器内 claude_code 必 FileNotFoundError | 🔴 阻塞 | 验收段 A 走 anthropic_api 绕开；段 B 用宿主机裸跑或改 Dockerfile |
| base_url 填错 → proxy 400 | 🟠 | 表单按 provider 预设填充 + 校验 |
| 纯 OpenAI 模型被误选 → 落 mock 无提示 | 🟠 | UI 隐藏 openai_api，或显式标「未实现」 |
| 新建 agent 默认 offline 显示离线 | 🟠 | §三：前端乐观置 online |
| 密钥明文（红线） | — | api_key 仅传后端加密存储，前端不留 |

## 十四、后端死注入链清理（解耦项，可选，不在前端合并 PR 内）

核对发现：`build_adapter()` 喂给 `ChatService` 的 `llm` 参数是死注入——ChatService 从不读 `self._llm`（`chat_service.py:59` 存了，line 98 却用 `build_adapter_for_agent` 重构）。

**可安全删除范围**：
- `chat_service.py:52` 参数 `llm` + `:59` `self._llm`
- `deps.py:92` 和 `:105` 两处 `get_llm_adapter()` 实参
- `chat.py:35` `_adapter` 单例 + `:69` 传参
- 连带 `deps.py:36 get_llm_adapter()`（删后无调用者）

**`build_adapter()` 函数本身（`factory.py:57`）暂留**：`self._llm` 名字在另一个类 `Coordinator`（`coordinator.py:16/26`，走 `chat_structured` 做任务分解）是活的，其注入源 M3 群聊才接线。删函数需待确认 M3 不依赖。

**纪律**：此项属后端重构，与前端合并解耦，**不并入前端合并 PR**（避免 scope 蔓延）。单独开 chore PR 处理。
