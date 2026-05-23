# IM 聊天式多 Agent 交互模式设计

> 清洗自: n8n @mentions 工作流、微软用户应用层、Claude Code 会话管理

## 一、n8n @mentions 参考实现分析

### 核心机制
```
用户输入: "@CodeReviewer 帮我审查这段代码"
                           ↓
            ┌──────────────┴──────────────┐
            ↓                              ↓
    提取 @AgentName                  提取消息内容
            ↓                              ↓
    查找 Agent 配置                  路由到目标 Agent
            ↓                              ↓
            └──────────────┬──────────────┘
                           ↓
                   Agent 执行并返回
```

### Agent 配置模型 (JSON Schema)
```json
{
  "agents": [
    {
      "name": "CodeReviewer",
      "model": "claude-sonnet-4-20250514",
      "provider": "anthropic",
      "instructions": "你是一个代码审查专家...",
      "personality": "严谨、直接",
      "capabilities": ["code_review", "diff_analysis"]
    }
  ]
}
```

## 二、AgentHub IM 交互模式设计

### 1. 单聊模式 (1对1)
- 用户选择一个 Agent 进行私聊
- 类似飞书/微信的 1对1 聊天
- Agent 流式返回消息
- 历史消息持久化

### 2. 群聊模式 (@mentions)
- 支持 @AgentName 触发特定 Agent
- 不 @ 的消息对所有 Agent 可见
- @All 触发所有群内 Agent 响应
- Agent 间可见彼此的回复（上下文共享）

### 3. 多会话并行
- 类似飞书的多会话切换
- 每个会话独立状态
- 跨会话的 Agent 可以共享知识库
- 任务状态全局可见

### 4. Agent 响应模式
| 触发方式 | 行为 | 适用场景 |
|---------|------|---------|
| **@单个Agent** | 仅该 Agent 响应 | 明确的单Agent任务 |
| **@多个Agent** | 所有 @ 的 Agent 响应 | 多视角审查 |
| **@All** | 群内所有 Agent 响应 | 全员讨论 |
| **无需 @** | 会话默认 Agent 响应 | 1对1 私聊 |

## 三、消息类型定义

```typescript
interface ChatMessage {
  id: string;
  sessionId: string;
  role: 'user' | 'agent' | 'system';
  agentName?: string;       // Agent 名称 (role=agent 时)
  content: string;
  mentions?: string[];       // @ 的 Agent 列表
  contentType: 'text' | 'code_diff' | 'file' | 'preview_url' | 'deploy_status';
  metadata?: {
    diff?: string;           // 代码 diff 内容
    previewUrl?: string;     // 预览 URL
    deployStatus?: string;   // 部署状态
    taskId?: string;         // 关联任务 ID
  };
  timestamp: string;
  status: 'sending' | 'sent' | 'streaming' | 'done' | 'error';
}
```

## 四、Agent 间通信模式

| 模式 | 实现 | 适用场景 |
|------|------|---------|
| **消息广播** | Redis Pub/Sub | Orchestrator → Workers |
| **直接引用** | 回复特定消息 | Agent 间协作 |
| **文件交换** | 共享工作区文件 | 代码开发流水线 |
| **状态共享** | Redis 状态存储 | 任务进度同步 |

## 五、用户体验流程

```
[用户输入消息]
      ↓
[解析 @mentions]
      ↓
┌─────┴─────┐
↓           ↓
单聊        群聊
↓           ↓
[路由到目标Agent]  [广播到所有@的Agent]
↓           ↓
[Agent 流式返回]    [各Agent并行返回]
↓           ↓
[实时渲染消息]      [消息聚合显示]
↓           ↓
[支持代码Diff内联预览]
[支持网页预览链接]
[支持一键部署按钮]
```
