# MCP-UI-frontend-V1.0-20260602 — MCP 接入前端 UI 切片

> ⚠️ **URL ERRATA（2026-06-03 整理）**：本文 API 前缀按全库现状统一为 **`/api/mcp/`**（**不带 `/v1/`**，见 [ADR-0003](../../../../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md)）。下方凡写 `/api/v1/mcp/...` 处一律以 `/api/mcp/...` 为准；冻结契约见 `docs/specs/04-commands §2.6`。

> **版本**：V1.0（2026-06-03 新增）
> **修订依据**：可行性清单 I-04 + 用户问询"相应的前端界面是否做了"
> **状态**：🟡 **未实现**。本文档为落地切片（要做什么），不是已实现的现状报告。
> **路径**：`src/frontend/src/`
> **单一权威入口**：[`../../README-REVISION.md`](../../README-REVISION.md)

---

## 0. 当前真实状态（2026-06-03 扫描）

| 检查 | 结果 |
|------|------|
| `find src/frontend -name "*mcp*"` | ❌ 0 命中 |
| `grep -rli "mcp"` 任何源文件 | ❌ 0 命中（仅 `provider_scanner.py` 后端 LLM 扫描，无关） |
| `AgentDetailPage.tsx` 现有 Tab 数 | 4（概览 / 能力 / 记忆 / 设置） |
| 是否有「MCP 接入」Tab | ❌ **无** |
| 是否有 `/mcp-market` 页面 | ❌ 无 `pages/` 目录 |
| 是否有 `/mcp-create` 页面 | ❌ |
| 是否有 `ToolCallBubble` 组件 | ❌ |
| 是否有 `mcpStore` | ❌ |

> **结论**：上一版计划默认"前端已就位"是**假象**。本切片是 P3 阶段要交付的清单。

---

## 1. 落地切片（3 页 + 1 Tab + 1 store + 6 组件）

### 1.1 路由注册（`routes.tsx` 新建）

> P3 启动时**第一个**改动。

```tsx
// src/frontend/src/routes.tsx  （新增）
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { McpMarketPage } from './pages/McpMarketPage'
import { McpMarketDetailPage } from './pages/McpMarketDetailPage'
import { McpCreatePage } from './pages/McpCreatePage'

export const router = createBrowserRouter([
  { path: '/', element: <AppShell />, children: [
    { index: true, element: <Navigate to="/chat" replace /> },
    { path: 'mcp-market', element: <McpMarketPage /> },
    { path: 'mcp-market/:mcpId', element: <McpMarketDetailPage /> },
    { path: 'mcp-create', element: <McpCreatePage /> },
    // 既有路由保留...
  ]}
])
```

```tsx
// src/frontend/src/main.tsx  （修改）
import { RouterProvider } from 'react-router-dom'
import { router } from './routes'
// 替换原 <App /> 套壳
```

### 1.2 入口改动（既有 `AppShell.tsx` / `LeftPanel.tsx` 扩展）

- **`components/layout/AppShell.tsx`**：用 `<Outlet />` 替代直接渲染，承接子路由
- **`components/layout/LeftPanel.tsx`**：在「技能」入口下新增「MCP 市场」入口项

### 1.3 3 个新页面

#### 1.3.1 `pages/McpMarketPage.tsx`（列表 + 搜索）
- 路径：`/mcp-market`
- 功能：F-001 列表 + F-002 搜索
- 数据源：`GET /api/v1/mcp/market`
- 组件：顶部搜索栏 + 标签筛选 + 分页 + `<McpServerCard />` 网格
- 复用：`components/ui/Card` / `Input`（既有） / `McpServerCard`

#### 1.3.2 `pages/McpMarketDetailPage.tsx`（详情 + 安装）
- 路径：`/mcp-market/:mcpId`
- 功能：F-003 详情 + F-004 安装入口
- 数据源：`GET /api/v1/mcp/market/{mcp_id}` + 触发 `POST /api/v1/mcp/installations`
- 组件：标题 + 描述 + 配置 schema 表单 + 标签 + `<McpInstallButton />`
- 复用：`McpInstallButton`（点击触发 mutation）

#### 1.3.3 `pages/McpCreatePage.tsx`（创建）
- 路径：`/mcp-create`
- 功能：F-018 stdio / F-019 sse+streamable_http
- 数据源：`GET /api/v1/mcp/market/templates`（F-022） + 提交 `POST /api/v1/mcp/servers`
- 组件：`<McpCreateForm />`（transport 切换）+ `<McpTemplateList />`（5 模板）
- 复用：`McpCreateForm` / `McpTemplateList`

### 1.4 1 个新 Tab：`components/agent/McpBindingPanel.tsx`

> 嵌在既有 `AgentDetailPage.tsx` 的 Tabs 列表里。

- 修改 `components/agent/AgentDetailPage.tsx`：
  - TABS 数组新增 `{ id: 'mcp-bindings', label: 'MCP 接入' }`
  - 新增 `{tab === 'mcp-bindings' && <McpBindingPanel agentId={...} />}`
- `McpBindingPanel` 内容：
  - 已绑定 MCP 列表（含启用/禁用开关）
  - 「+ 绑定 MCP」按钮 → 弹出选择器（已安装 MCP instance）
  - 解绑按钮 → `DELETE /api/v1/mcp/bindings/{id}`（F-010）
- 数据源：`GET /api/v1/mcp/bindings?agent_id=...`（**新增端点**） / `POST/DELETE`

> **新增 1 个 GET 端点** `GET /api/v1/mcp/bindings?agent_id=...`：列出某 agent 的所有绑定。本期 IC-MCP §1.3 暂列"绑定"为 2 个 POST/DELETE 端点；GET 列表是 P3 阶段补的。需在 P3 启动时同步 PR-01。

### 1.5 1 个新 store：`stores/mcpStore.ts`

```ts
// Zustand（项目既有风格）
interface McpStore {
  servers: Record<string, MCPServer>           // mcp_id → 详情缓存
  installations: Record<string, Installation>   // installation_id → 安装
  bindings: Record<string, Binding>             // binding_id → 绑定
  toolCalls: Record<string, ToolCall>           // trace_id → 工具调用
  // actions
  loadMarket: (q?: string) => Promise<void>
  loadDetail: (mcpId: string) => Promise<void>
  install: (req: InstallReq) => Promise<Installation>
  uninstall: (installationId: string) => Promise<void>
  bind: (req: BindReq) => Promise<Binding>
  unbind: (bindingId: string) => Promise<void>
  loadBindings: (agentId: string) => Promise<void>
  loadToolCalls: (traceId: string) => Promise<void>
}
```

### 1.6 6 个新组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `McpServerCard` | `components/mcp/McpServerCard.tsx` | 列表卡片（图标 + 名称 + 标签 + 官方标） |
| `McpInstallButton` | `components/mcp/McpInstallButton.tsx` | 一键安装按钮（含 loading/success/error 态） |
| `McpCreateForm` | `components/mcp/McpCreateForm.tsx` | 创建表单（transport 切换 + schema 动态渲染 + 干跑按钮） |
| `McpTemplateList` | `components/mcp/McpTemplateList.tsx` | 5 模板卡片列表 |
| `ToolCallBubble` | `components/mcp/ToolCallBubble.tsx` | 工具调用展示气泡（参数/结果/耗时/状态） |
| `McpAuditPanel` | `components/mcp/McpAuditPanel.tsx` | 审计日志面板（嵌入 McpBindingPanel 底部） |

### 1.7 1 个 api wrapper：`api/mcp.ts`

```ts
// src/frontend/src/api/mcp.ts  （新增）
const API = '/api/mcp'   // 全库无 /v1/，对齐 /api/agents（ADR-0003）

export const mcpApi = {
  listMarket: (q: ListMarketQuery) => fetch(`${API}/market?...`).then(...),
  getDetail: (mcpId: string) => fetch(`${API}/market/${mcpId}`).then(...),
  listTemplates: (workspaceId: string) => fetch(`${API}/market/templates?workspace_id=...`).then(...),
  install: (req: InstallReq) => fetch(`${API}/installations`, { method: 'POST', body: JSON.stringify(req) }).then(...),
  uninstall: (id: string) => fetch(`${API}/installations/${id}`, { method: 'DELETE' }).then(...),
  bind: (req: BindReq) => fetch(`${API}/bindings`, { method: 'POST', body: JSON.stringify(req) }).then(...),
  unbind: (id: string) => fetch(`${API}/bindings/${id}`, { method: 'DELETE' }).then(...),
  listBindings: (agentId: string) => fetch(`${API}/bindings?agent_id=${agentId}`).then(...),
  create: (req: CreateReq) => fetch(`${API}/servers`, { method: 'POST', body: JSON.stringify(req) }).then(...),
}
```

### 1.8 1 处嵌入：`components/chat/MessageBubble.tsx`

- 在 `MessageBubble` 内部，agent 消息的 content 块里检测 `tool_calls` 字段
- 若有 → 渲染 `<ToolCallBubble toolCall={...} />`
- 数据源：现有 `chatStore` 的 `messages[].tool_calls`（**chatStore 需扩展字段**：现有已含 `tool_calls`，需确认）

---

## 2. UI 关键交互流

### 2.1 浏览并安装 MCP

```
LeftPanel 点击「MCP 市场」
  ↓
/mcp-market (McpMarketPage)
  ├─ 搜索 q=filesystem
  ├─ 标签筛选 tag=fs
  └─ 点击 McpServerCard
       ↓
/mcp-market/:mcpId (McpMarketDetailPage)
  ├─ 详情渲染
  └─ 点击 McpInstallButton
       ├─ instance_name 输入
       ├─ config_overrides 输入（可选）
       └─ POST /api/v1/mcp/installations
            ↓
       弹 toast「安装中」→ 5s 内 ready → toast「安装成功」
```

### 2.2 绑定到 Agent

```
RightPanel 点击 Agent
  ↓
AgentDetailPage 切到「MCP 接入」Tab (McpBindingPanel)
  ├─ 显示已绑定列表
  ├─ 「+ 绑定」按钮 → 弹出选择器（已安装 installation）
  └─ POST /api/v1/mcp/bindings
       ├─ 后端调 mcp_injector.attach_mcp(...)
       └─ Runtime 进程 MCP config 注入
```

### 2.3 工具调用展示

```
用户在 IM 会话输入消息
  ↓
agent 处理 → 通过 Runtime 调用 MCP tool
  ↓
Runtime → WS tool_call_request → 后端
  ↓
后端 → WS 广播到 IM 会话
  ↓
MessageBubble 渲染 ToolCallBubble
  ├─ 显示 tool_name / args / duration / result
  └─ 失败显示 error_code + error_message
```

---

## 3. 视觉与可访问性

- 沿用既有 `components/ui/` 组件库（Button / Card / Tabs / Dialog / Input / ...）
- 沿用既有 Tailwind token（颜色 / 间距 / 字号）
- **不引**新视觉库（shadcn / radix / material）
- 关键交互组件需有 `aria-label`（WCAG 2.2 A 级）
- 键盘可访问（Tab 顺序 / Enter 触发）
- 不引 Lottie / Framer Motion（既有无）

---

## 4. 状态与缓存

- 全部用 Zustand（`mcpStore`），与既有 `chatStore` 风格一致
- 不引 React Query / SWR（保持栈最小）
- 列表缓存 5min（与后端 Redis TTL 对齐）
- 工具调用实时数据走既有 WS 通道

---

## 5. 端到端验收（P3 收束前）

- [ ] `/mcp-market` 列表渲染 5+ MCP，搜索/筛选/分页正常
- [ ] `/mcp-market/:mcpId` 详情加载 ≤ 1.5s（S-01）
- [ ] `/mcp-create` 三种 transport 表单切换 + 干跑成功
- [ ] AgentDetailPage「MCP 接入」Tab 渲染 + 绑定/解绑生效
- [ ] IM 会话中 `ToolCallBubble` 实时显示
- [ ] 键盘可访问（Tab + Enter）
- [ ] `pnpm run lint` 通过
- [ ] `pnpm run typecheck` 通过
- [ ] 真实浏览器（headless Chrome）截图核验

---

## 6. 不在本期范围（前端层）

- ❌ MCP 创建的 Monaco / YAML 编辑器（本期只用 `<Input>` + JSON 字符串）
- ❌ 工具调用可视化链路图（仅 ToolCallBubble 文本）
- ❌ 模板市场（B-13，本期仅官方 5 模板内置）
- ❌ 多语言切换（沿用项目既有 i18n）
- ❌ 移动端响应式优化（沿用既有 grid 即可）

---

*本 MCP-UI-frontend 是 MCP 接入**前端落地**唯一权威。P3 阶段按本切片交付；任何与本切片冲突的 22 模块/132 异常文档作废。*
