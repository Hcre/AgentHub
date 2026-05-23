# Claude Agent SendMessage 深度分析

## 问题 1: 长对话如何实现？

### AgentPipe 的实现方式

**答案：不支持真正的长对话维持**

AgentPipe 的 `ClaudeAgent.SendMessage()` 方法每次调用都会：
1. 创建一个**全新的** CLI 进程
2. 将所有历史消息作为 **Prompt 文本** 传递给 CLI
3. CLI 执行一次对话后退出

```go
// claude.go 第 104-158 行
func (c *ClaudeAgent) SendMessage(ctx context.Context, messages []agent.Message) (string, error) {
    // 1. 构建提示词（包含所有历史消息）
    prompt := c.buildPrompt(relevantMessages, true)
    
    // 2. 每次都创建新进程
    cmd := exec.CommandContext(ctx, c.execPath, args...)
    cmd.Stdin = strings.NewReader(prompt)
    
    // 3. 执行并退出
    output, err := cmd.CombinedOutput()
    return string(output), err
}
```

### 长对话模拟机制

虽然不能真正维持长对话，但 AgentPipe 通过 `buildPrompt()` 方法**模拟**了多轮对话：

```go
// claude.go 第 245-317 行
func (c *ClaudeAgent) buildPrompt(messages []agent.Message, isInitialSession bool) string {
    var prompt strings.Builder
    
    // PART 1: Agent 角色定义
    prompt.WriteString("AGENT SETUP:\n")
    prompt.WriteString(fmt.Sprintf("You are '%s' participating in a multi-agent conversation.\n\n", c.Name))
    prompt.WriteString("YOUR ROLE AND INSTRUCTIONS:\n")
    prompt.WriteString(c.Config.Prompt)
    
    // PART 2: 完整的对话历史
    if len(messages) > 0 {
        prompt.WriteString("CONVERSATION SO FAR:\n")
        for _, msg := range otherMessages {
            prompt.WriteString(fmt.Sprintf("[%s] %s: %s\n", timestamp, msg.AgentName, msg.Content))
        }
    }
    
    return prompt.String()
}
```

**问题**：
- 每次调用 `SendMessage` 都会重新发送**完整的对话历史**
- Claude CLI 每次都认为是新的对话
- 无法利用 Claude 的会话状态（如之前的修改上下文）

---

## 问题 2: exec.CommandContext 详细分析

### 核心代码

```go
// claude.go 第 129-133 行
args := []string{}

// 可选：添加模型参数
if c.Config.Model != "" {
    args = append(args, "--model", c.Config.Model)
}

// 创建命令上下文
cmd := exec.CommandContext(ctx, c.execPath, args...)
cmd.Stdin = strings.NewReader(prompt)

// 执行并获取输出
output, err := cmd.CombinedOutput()
```

### 参数详解

| 组件 | 说明 |
|------|------|
| `ctx` | Go 的 context.Context，用于超时控制和取消 |
| `c.execPath` | Claude CLI 的路径（通过 `exec.LookPath("claude")` 查找） |
| `args` | CLI 参数数组 |
| `cmd.Stdin` | 通过标准输入传递 Prompt |
| `cmd.CombinedOutput()` | 合并 stdout 和 stderr 输出 |

### exec.CommandContext 的关键特性

```go
// 1. 超时控制
ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
defer cancel()
cmd := exec.CommandContext(ctx, "claude", args...)

// 2. 取消执行
// 当 ctx 被 cancel 时，进程会被终止
select {
case <-ctx.Done():
    return ctx.Err()  // 用户取消或超时
default:
    cmd.Run()
}
```

### Claude CLI 调用方式对比

| 方式 | 命令示例 | 特点 |
|------|----------|------|
| **AgentPipe** | `claude --model xxx < prompt.txt` | 通过 stdin 传递，stdout 输出 |
| **cc-haha** | `claude --print --sdk-url ws://... --session-id xxx --input-format stream-json --output-format stream-json` | 完整的会话管理 |

---

## cc-haha 的正确实现（参考）

cc-haha 使用了 `--session-id` 和 `--resume` 参数来真正维持会话：

```typescript
// conversationService.ts 第 106-143 行
private buildSessionCliArgs(
  sessionId: string,
  sdkUrl: string,
  shouldResume: boolean,
  options?: SessionStartOptions,
): string[] {
  return [
    '--print',                      // 非交互模式
    '--verbose',
    '--sdk-url', sdkUrl,           // WebSocket 地址
    '--input-format', 'stream-json',
    '--output-format', 'stream-json',
    '--include-partial-messages',
    
    // 关键：会话管理
    ...(shouldResume 
      ? ['--resume', sessionId]    // 恢复已有会话
      : ['--session-id', sessionId] // 创建新会话
    ),
    
    // 其他参数...
    ...this.getRuntimeArgs(options),
  ]
}
```

### 会话维持原理

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code CLI                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  会话状态管理器 (Session Manager)                     │   │
│  │  - session_id → 会话目录 (~/.claude/sessions/)       │   │
│  │  - 消息历史 (transcript.jsonl)                       │   │
│  │  - 工作目录上下文                                     │   │
│  │  - 之前的修改状态                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↑
                    --session-id xxx
                    --resume xxx
```

---

## AgentPipe 与 cc-haha 对比

| 特性 | AgentPipe | cc-haha |
|------|-----------|---------|
| **会话维持** | ❌ 每次新建进程 | ✅ 使用 `--session-id` |
| **历史消息** | 每次作为 Prompt 传递 | CLI 内部管理 |
| **上下文保持** | ❌ 无法保持文件修改状态 | ✅ 保持 |
| **通信方式** | stdin/stdout 单次调用 | WebSocket 流式通信 |
| **进程管理** | 每次执行后退出 | 长驻进程 |

---

## AgentPipe 长对话的解决方案

如果需要在 AgentPipe 中实现真正的长对话，有以下方案：

### 方案 1: 修改为长驻进程 + WebSocket

```go
type ClaudeAgent struct {
    agent.BaseAgent
    execPath string
    
    // 新增：长驻进程
    proc       *exec.Cmd
    sessionId  string
    sdkUrl     string
    mu         sync.Mutex
}

func (c *ClaudeAgent) SendMessage(ctx context.Context, messages []agent.Message) (string, error) {
    // 通过已启动的 CLI 进程发送消息
    c.mu.Lock()
    defer c.mu.Unlock()
    
    // 构建 stream-json 格式的消息
    msg := buildStreamJsonMessage(messages)
    
    // 通过 stdin 发送
    _, err := c.proc.Stdin.Write([]byte(msg + "\n"))
    if err != nil {
        return "", err
    }
    
    // 通过 channel 等待响应
    response := <-c.responseChan
    return response, nil
}
```

### 方案 2: 使用 CLI 的 --resume 参数

```go
func (c *ClaudeAgent) SendMessage(ctx context.Context, messages []agent.Message) (string, error) {
    // 检查是否有已有会话
    if c.sessionId == "" {
        c.sessionId = generateSessionId()
    }
    
    args := []string{
        "--session-id", c.sessionId,      // 维持会话
        "--resume", c.sessionId,           // 恢复上下文
    }
    
    prompt := c.buildPrompt(messages, false) // false = 不是初始会话
    
    cmd := exec.CommandContext(ctx, c.execPath, args...)
    cmd.Stdin = strings.NewReader(prompt)
    
    output, err := cmd.CombinedOutput()
    return string(output), err
}
```

---

## 总结

### AgentPipe 的设计局限

1. **每次新建进程**：无法维持长对话状态
2. **Prompt 传递历史**：上下文长度受限于 Prompt 长度
3. **单次调用模式**：适合简单的 Agent 协作，但不适合复杂的交互式对话

### cc-haha 的设计优势

1. **长驻进程**：CLI 进程持续运行
2. **会话管理**：通过 `--session-id` 维持会话
3. **流式通信**：通过 WebSocket 实现实时交互
4. **状态保持**：文件修改、工具执行状态等可保持

如果需要在 AgentPipe 中实现类似 cc-haha 的能力，需要重构为长驻进程模式并引入 WebSocket 通信。
