# AgentHub 边界矩阵

> 版本: v2.1 | Always（自动）/ Ask First（需审批）/ Never（硬禁止）

---

## 零、审批模式

### 0.1 全局审批模式设置

用户可在全局设置中切换审批模式，影响所有 Agent 的操作行为：

| 模式 | Agent 工作区操作 | 危险操作 | Claude Code 内置权限 | 适用场景 |
|------|:---:|:---:|:---:|------|
| **正常模式**（默认） | Always | Ask First | 捕获 → 转 AgentHub 审批卡片 | 日常开发 |
| **执行模式** | Always | Always | `--dangerously-skip-permissions` | 信任的批量任务 |

### 0.2 CLI 权限处理（v4: permission_denials 检测方案）

> v4 更新：`--print` 模式非交互式，CLI 不产出 `permission_request` 事件，也不等待 stdin 输入。改为事后检测 `permission_denials` + `bypassPermissions` 重试。

```
CLI 执行危险操作（如 Bash: rm -f /tmp/build）
  │
  ├─ CLI 阻断 → tool_result: {is_error: true, content: "was blocked..."}
  ├─ 多次重试后耗尽 → result: {is_error: true, permission_denials: [...]}
  │
  ▼
ChatService 检测 DONE event 中的 permission_denials
  │
  └─ emit REQUEST_APPROVAL → 前端审批卡片
       │
       ├─ 用户 [信任并重试] → ChatService 重新调用
       │   CLI: --permission-mode bypassPermissions
       │
       ├─ 用户 [换个方式] → ChatService 重新调用
       │   stdin: feedback 文本 + 安全方式要求
       │
       └─ 用户 [忽略] → 消息卡片折叠，不重试
```

### 0.3 权限模式配置

| Agent `permission_mode` | CLI `--permission-mode` | 行为 |
|------------------------|------------------------|------|
| `acceptEdits`（推荐默认） | `--permission-mode acceptEdits` | 编辑自动通过，Bash/git 等被阻断 |
| `bypassPermissions` | `--permission-mode bypassPermissions` | 全自动，不阻断 |

---

## 一、Agent 管理

### 1.1 Agent 创建

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| 选择 Agent 系统 (claude/codex/trae) | Always | 三个系统之一必选 |
| 填写 name/avatar/role | Always | name 全局唯一，重复创建拒绝 |
| 配置 provider/model/api_key | Always | api_key 前端密码模式输入，AES-256-GCM 加密存储 |
| 配置 base_url（自定义端点） | Always | 可选，不填则用 provider 默认端点 |
| 填写 skills/system_prompt/capability_tags | Always | 可选，不填则用系统默认模板 |
| 对话式创建（自然语言→草案→确认） | Always | 系统仅生成草案，最终由用户确认 |
| 删除 Agent | Ask First | 确认弹窗。自动从所有群组移除。影响的旧 @mention 失效需提示 |
| 重置 API Key | Ask First | api_key 不可查看明文，仅支持重置 |
| 修改 Agent name | Ask First | 提示：旧对话中 @mention 将失效 |

### 1.2 Agent 详情页

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| 查看概览/能力/任务/活动/群组 Tab | Always | 只读 |
| 编辑 capability_tags | Ask First | 影响协调者任务匹配 |
| 编辑记忆 (L1-L4) | Ask First | 可能影响上下文注入 |
| 修改 settings (max_tokens/并发数) | Ask First | |

---

## 二、群组管理

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| 创建群组 | Always | 自动生成协调者 Agent（系统蓝标，不可移除） |
| 添加 Agent 到群组 | Always | Agent 已在群组中? → 拒绝 |
| 移除 Agent 从群组 | Ask First | 确认弹窗 |
| 删除群组 | Ask First | 级联删除协调者 + 关闭群聊会话 |
| @协调者 发送任务 | Always | 显式触发 |
| 无@ 自动检测任务意图 | Always | LLM 快速分类判断 |
| @AgentName 直接路由 | Always | 协调者不介入 |
| 单群组 Agent 上限 | Never | > 20 个拒绝添加 |

---

## 三、任务管理

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| 聊天中派发任务（自动/显式） | Always | 协调者自动分解 |
| 手动创建任务 | Always | 填写 title + 可选 assignee |
| 任务状态自动流转 | Always | FSM Guard 校验后执行 |
| 子任务嵌套深度 > 1 | Never | 不支持子任务的子任务 |
| 修改任务分配 | Ask First | 可能中断执行中的 Agent |

---

## 四、收件箱与审批

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| Agent 请求审批（删文件/push/部署/外网） | Always | 自动创建 Notification → 收件箱 Badge+1 |
| 用户 APPROVE | Ask First | Agent 恢复执行 |
| 用户 REJECT | Ask First | 任务 CANCELLED |
| 用户 EDIT（修改后继续） | Ask First | checkpoint 合并编辑内容 → Agent 继续 |
| 用户 RESPOND（补充信息） | Ask First | human_input 注入 → Agent 重新处理 |
| 审批超时（24h） | Always | 自动 REJECT → CANCELLED |
| 查看收件箱 | Always | 按分类筛选 |
| 标记已读 | Always | 批量/单条 |

---

## 五、文件操作

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| 读取项目文件 | Always | 只读 |
| 创建/编辑文件 | Always | 无需审批 |
| 删除文件 | Ask First | 弹窗确认 + 文件路径 + 内容预览 |
| Git push | Ask First | 展示 commit log + diff |
| Docker 部署 | Ask First | 展示部署预览 |
| 访问外部网络 | Ask First | 每次展示 URL |
| 路径遍历 ../ | Never | 路径规范化拒绝 |
| 读写 .env / .git/config / credentials.* | Never | 黑名单拒绝 |
| 单次写入 > 1MB | Never | 拒绝 |

---

## 六、安全

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| JWT 认证 | Always | 所有 API + WS 需有效 token |
| API Key 加密存储 | Always | AES-256-GCM，明文不可查看 |
| API Key 输入后查看明文 | Never | 仅支持重置 |
| 速率限制 | Always | 60 req/min/IP |
| SQL 参数化 | Always | 禁止裸 SQL |
| print() / console.log() 生产路径 | Never | logging 模块 |
| 硬编码密钥 | Never | 环境变量注入 |

---

## 七、Agent 执行

| 操作 | 级别 | 条件与约束 |
|------|------|-----------|
| LLM 调用 | Always | 通过 L1 Adapter，禁止直接调用 |
| Token 预算超限 | Always | 四道硬闸自动终止 |
| 工具调用上限 | Always | 单任务 10 次 |
| Harness 含 LLM 调用 | Never | 架构红线 |
| Worker 间直接通信 | Never | 仅通过 Blackboard + Coordinator |

---

## 八、关键数值边界

| 边界 | 值 |
|------|-----|
| 单个群组 Agent 上限 | 20 |
| 单会话热上下文 | 最近 20 条 |
| 单 Agent 并发任务 | 默认 3 |
| 子任务嵌套深度 | 1 层 |
| 消息长度上限 | 10000 字符 |
| Pin 消息上限 | 10 条/会话 |
| 审批超时 | 24h |
| 重试次数上限 | 3 次 |
| Token 每日预算 | 可配置，默认 1,000,000 |
| 速率限制 | 60 req/min/IP |
| WebSocket 心跳 | 30s，3 次无响应断开 |
