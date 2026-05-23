# Claude Code vs Codex 详细对比

> 清洗自: Claude Code SDK 文档 + Codex CLI README + Codex 官方介绍

## 一、基本属性对比

| 属性 | Claude Code | Codex CLI |
|------|------------|-----------|
| **开发商** | Anthropic | OpenAI |
| **开源** | 部分开源 (Agent SDK) | 开源 (Apache 2.0) |
| **安装方式** | npm / 独立安装包 | npm / Homebrew |
| **运行环境** | Node.js | Node.js |
| **底层模型** | Claude 系列 | codex-1 / GPT 系列 |
| **API 协议** | Anthropic Messages API | OpenAI Chat Completions API |
| **MCP 支持** | ✓ 原生 Client + Server | ✓ 支持 |

## 二、Agent 能力对比

| 能力 | Claude Code | Codex CLI |
|------|------------|-----------|
| **代码生成** | ✓ | ✓ |
| **文件操作** | read_file, write_file, edit_file, apply_patch | 文件系统直接操作 |
| **命令执行** | exec_shell / bash | 终端命令 |
| **Git 操作** | git_status, git_diff, git_log, git_show 等 | 通过终端执行 git |
| **代码审查** | ✓ (review 工具) | ✓ |
| **测试运行** | ✓ (run_tests) | 通过终端执行 |
| **网页搜索** | web_search | 依赖 Codex Web |
| **子Agent** | ✓ (agent_open/eval/close) | ✗ 原生不支持 |
| **会话管理** | ✓ Session (多会话并行) | ✓ Session-based |
| **流式输出** | ✓ SSE | ✓ SSE |
| **结构化输出** | ✓ JSON Schema | ✓ JSON Mode |
| **审批流程** | ✓ Permission Modes | ✓ |
| **插件系统** | ✓ Plugins | ✗ |
| **技能系统** | ✓ Skills | ✗ |

## 三、工具调用对比

| 工具类别 | Claude Code | Codex CLI |
|---------|------------|-----------|
| **规划工具** | checklist_write, update_plan | ✗ (依赖 LLM) |
| **搜索工具** | grep_files, file_search | 通过终端 grep/find |
| **Web 工具** | web_search, fetch_url, web.run | 依赖 Codex Web |
| **Agent 工具** | agent_open, agent_eval, agent_close | ✗ |
| **Git 工具** | git_status, git_diff, git_log, git_show, git_blame | 终端执行 |
| **验证工具** | validate_data, diagnostics | 终端执行 |
| **Shell 工具** | exec_shell (foreground/background) | 终端执行 |
| **编辑工具** | edit_file, apply_patch, write_file | 文件操作 + sed |
| **通知工具** | notify | ✗ |

## 四、适配器层统一接口设计

```typescript
interface UnifiedAgent {
  // 基础方法
  sendMessage(prompt: string): AsyncIterable<StreamEvent>;
  
  // 文件操作
  readFile(path: string): Promise<string>;
  writeFile(path: string, content: string): Promise<void>;
  editFile(path: string, search: string, replace: string): Promise<void>;
  
  // 命令执行
  execCommand(command: string): Promise<ExecResult>;
  
  // Git 操作
  gitStatus(): Promise<GitStatus>;
  gitDiff(): Promise<string>;
  
  // 子Agent (Claude Code 原生支持, Codex 通过 Orchestrator 模拟)
  createSubAgent(config: SubAgentConfig): Promise<SubAgent>;
  
  // 会话管理
  createSession(): Promise<Session>;
  getSession(id: string): Promise<Session>;
}
```

## 五、AgentHub 统一适配策略

| 差异点 | 适配策略 |
|--------|---------|
| API 协议不同 | LiteLLM 统一网关 |
| 工具集差异 | 最小公共接口 + 扩展检测 |
| 子Agent 差异 | Orchestrator 层实现，Codex 通过多会话模拟 |
| 文件操作差异 | 统一 Virtual FS 抽象 |
| 流式输出差异 | 统一 SSE → IM 消息流适配 |
| 认证差异 | 统一 Auth Proxy |
