# API Key 管理器设计

## 问题

创建 Agent 时每次都要手动复制粘贴 API Key，切换模型/Provider 反复输入。

## 方案：localStorage 本地管理

### 为什么不存后端

- **零安全风险**：Key 只存浏览器，不经过网络传输/存储
- **零后端改动**：纯前端功能，不需要新表、加密、权限
- **即改即用**：刷新不丢（Zustand persist）

### 数据模型

```typescript
interface ApiKeyEntry {
  id: string           // 唯一 ID
  name: string         // 用户命名，如 "我的 DeepSeek"
  provider: string     // 提供商，如 deepseek / openai / anthropic
  keyPrefix: string    // 前 4 位，用于展示
  key: string          // 完整 Key（存 localStorage，不发送给后端）
  createdAt: number    // 添加时间戳
}
```

Zustand store: `useApiKeyStore`，persist 到 localStorage key `agenthub-apikeys`。

### UI 设计

**1. API Key 管理页**（独立 Section，左侧导航可进入）

```
┌──────────────────────────────────┐
│ ← 返回    API 密钥管理            │
│                                   │
│ [+ 添加密钥]                      │
│                                   │
│ ┌───────────────────────────────┐ │
│ │ DeepSeek V3    deepseek  🔑4a | │
│ │ 添加于 5/26              [删除]│ │
│ └───────────────────────────────┘ │
│ ┌───────────────────────────────┐ │
│ │ 硅基流动       openai    🔑sk-│ │
│ │ 添加于 5/26              [删除]│ │
│ └───────────────────────────────┘ │
└──────────────────────────────────┘
```

**2. 添加/编辑弹窗**

```
┌──────────────────────┐
│ 添加 API 密钥         │
│                      │
│ 名称: [我的 DeepSeek] │
│ 提供商: [deepseek  ▾ ]│
│ API Key: [*****     ] │
│                      │
│ [取消]  [保存]        │
└──────────────────────┘
```

**3. 创建 Agent 页改造**

```
之前：API Key: [________________] (手动粘贴)

之后：API Key: [我的 DeepSeek ▾]  [管理密钥 →]
              │ 硅基流动          │
              │ + 添加新密钥      │
```

- 下拉框列出已存 Key
- 选 "自定义输入" 时回退到文本框
- "管理密钥 →" 跳转到管理页

### 文件清单

| 文件 | 说明 |
|------|------|
| `src/frontend/src/stores/apiKeyStore.ts` | Zustand persist store |
| `src/frontend/src/components/settings/ApiKeyManager.tsx` | 管理页面 |
| `src/frontend/src/components/settings/ApiKeyDialog.tsx` | 添加/编辑弹窗 |
| `src/frontend/src/stores/uiStore.ts` | 加 `api-keys` section |
| `src/frontend/src/components/layout/CenterPanel.tsx` | 加路由 |
| `src/frontend/src/components/agent/CreateAgentModal.tsx` | 改造 Key 输入 |
| `src/frontend/src/components/agent/CustomAgentModal.tsx` | 改造 Key 输入 |

### 不影响范围

- 后端零改动
- Agent 创建 API 不变（仍接收 apiKey 字符串）
- 已有 Agent 的 Key 配置不受影响
