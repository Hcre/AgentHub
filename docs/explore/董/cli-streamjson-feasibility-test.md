# CLI 长驻 + stream-json 可行性验证

> 日期：2026-05-29 | 状态：**已完成 — Go with caveat（V1-V5 全部验证）**
> 上游：[group-chat-pipeline-proposal.md §四 Phase 0.5](./董/group-chat-pipeline-proposal.md)
> 目的：验证 Claude CLI 的 `--input-format stream-json --output-format stream-json` 模式能否支撑长驻多轮交互
> 结论：V1/V2/V3/V5 通过，V4 部分通过。**长驻 + stream-json 方案 Go**，但 Phase 1 实施时必须解决 caveat（详见 §七）

## 一、为什么需要这份验证

`claude --help` 显示：
- `--print` 文档说明是「Print response and exit」
- `--input-format stream-json` 文档说明是「realtime streaming input」

两者语义**潜在冲突**：到底是「读完所有 stdin 后处理一次然后退出」，还是「边读 stdin 边响应、不退出」？

cc-haha 项目的代码看起来是长驻模式，但 cc-haha 用了 WebSocket（`--sdk-url`），不是直接 stdin。**我们不打算引入 SDK WebSocket**，需要确认 stdin pipe 也能达到同样效果。

不验证就直接动 Runtime 改造 = 赌博。

## 二、验证项（5 个）

### V1：CLI 是否在收到一条 user 消息处理完后保持 stdin 监听

**假设**：进程在输出 `{"type":"result"...}` 后**不退出**，继续等待 stdin 下一条 JSONL。

**方法**：
```bash
# 启动 CLI，准备好两条消息分两次写入
python scripts/feasibility/v1_persistent_stdin.py
```

脚本逻辑：
1. spawn `claude --print --input-format stream-json --output-format stream-json --verbose --session-id <uuid> --system-prompt "你是测试助手"`
2. 写入第一条 `{"type":"user","message":{"role":"user","content":"说 hello"}}\n`
3. 读 stdout 直到 `{"type":"result"}` 事件
4. **不关闭 stdin**，等待 5 秒后写入第二条 `{"type":"user","message":{"role":"user","content":"说 world"}}\n`
5. 观察：
   - 进程在第一条 result 后是否仍 alive（`proc.poll() is None`）
   - 第二条消息后是否有新的 assistant 输出

**预期判定**：
- ✅ 通过：进程在第一条 result 后保持运行，第二条 user message 后产生新 assistant 输出
- ❌ 失败：进程在第一条 result 后退出（returncode 非 None）

**失败后果**：长驻方案不可行。需要回退到 v2 的「ContextBuilder 内自实现 messages 时间交错」，但 CLI 路径的 `_extract_prompt` 改造死结仍待解，可能意味着群聊路径暂时无法获得 messages role 分层的好处。

---

### V2：长驻进程内的对话记忆是否累积

**假设**：在 V1 通过的前提下，第二条 user message 时 CLI 仍记得第一条对话内容。

**方法**：
1. 同 V1 启动方式
2. 第一条 user：「我叫张三」
3. 等 result
4. 第二条 user：「我叫什么？」
5. 检查第二条的 assistant 回复是否包含「张三」

**预期判定**：
- ✅ 通过：第二条回复识别出「张三」
- ❌ 失败：第二条回复说「不知道」/「未提供姓名」

**失败后果**：CLI 内部并非按消息累积，stream-json 模式可能只是「每条 stdin 当作独立请求」。此时长驻除了节省冷启动外没有任何对话历史优势，反而比 `--resume` 更弱。需要重新评估。

---

### V3：`--system-prompt` 的持久性

**假设**：首次 spawn 时传入的 `--system-prompt` 在多条 user 消息之间都生效。

**方法**：
1. spawn 时 `--system-prompt "你是「测试助手」，每次回复开头必须写「[测试助手]」"`
2. 连续推送 5 条不同的 user message
3. 检查 5 次 assistant 回复是否都以 `[测试助手]` 开头

**预期判定**：
- ✅ 全部 5 次都有 `[测试助手]` 前缀
- ⚠️ 部分通过：前几次有，后面衰减 → 需要附加 reminder 注入策略
- ❌ 全部失败 → 长驻模式下 system prompt 失效，可能需要每次 user 消息前注入一个 reminder

**失败后果**：身份强化策略要从「首次 spawn 注入」改为「每条 user 消息前附加 reminder 块」，Runtime 推送逻辑要相应调整。

---

### V4：异常退出与 stderr 捕获

**假设**：CLI 子进程异常退出时，IM 层能感知（returncode != 0 或 stderr 有内容）。

**方法**：
1. 启动长驻 CLI
2. 推送 1 条 user，等 result
3. 主动 `kill -9` CLI 进程
4. 进程父端尝试再次写入第三条 user message，观察：
   - asyncio 是否抛出 `BrokenPipeError` 或类似异常
   - `proc.returncode` 是否非 None
   - stderr 是否有内容

**附加测试**：发送格式错误的 JSONL（如 `{not json}\n`），观察 CLI 是否退出、退出码、stderr 内容。

**预期判定**：
- ✅ 通过：父端能稳定检测子进程死亡，捕获到 `BrokenPipeError` 或 returncode
- ❌ 失败：父端可能 hang 在 stdin write 上 → 需要加 stdin write timeout 和 watchdog

**失败后果**：Pool 实现必须加 watchdog 心跳，每次 send 前先检查进程健康度，增加实现复杂度。

### V5：`--resume` + `--input-format stream-json` 崩溃恢复兼容性

**假设**：CLI 用 `--session-id <key>` 首次 spawn → 产生会话（写入 `~/.claude/sessions/<key>/`）→ kill 进程 → 用 `--resume <key>` + `--input-format stream-json` 重连后能恢复对话历史。

**方法**：
1. spawn `claude --print --input-format stream-json --session-id <uuid> --system-prompt "你是 Alice"`
2. 推送：「我叫 Bob，代号 BLUE42，最喜欢的颜色是绿色。请记住。」
3. 等 result
4. 推送：「我叫什么名字？代号是什么？」以确认 CLI 记住了
5. `kill -9` 杀掉进程
6. 重新 spawn：`claude --print --input-format stream-json --resume <uuid>`（不带 `--session-id`，否则 CLI 报错要求 `--fork-session`）
7. 推送：「我刚才叫什么名字？代号和最喜欢的颜色是什么？」
8. 检查回复中是否包含 Bob / BLUE42 / 绿色

**预期判定**：
- ✅ 通过：resume 后 CLI 记得 Bob、BLUE42、绿色 — crash recovery 可用此路径
- ❌ 失败：resume 后 CLI 不记得之前对话 — 需自实现"补灌历史"机制

**失败后果**：Phase 1 crash recovery 不可依赖 `--resume`，需要 proc 崩溃后重 spawn + 逐条补灌该 Agent 所有历史消息。

---

## 三、验证脚本组织

```
scripts/feasibility/
├── README.md                       # 如何跑、如何解读结果
├── _common.py                      # 共享：spawn CLI、读 JSONL、超时管理
├── v1_persistent_stdin.py
├── v2_memory_accumulation.py
├── v3_system_prompt_persistence.py
├── v4_failure_detection.py
└── v5_resume_recovery.py           # 新增
```

```
scripts/feasibility/
├── README.md                       # 如何跑、如何解读结果
├── _common.py                      # 共享：spawn CLI、读 JSONL、超时管理
├── v1_persistent_stdin.py
├── v2_memory_accumulation.py
├── v3_system_prompt_persistence.py
└── v4_failure_detection.py
```

每个脚本输出结构化 JSON 报告：
```json
{
  "test_id": "V1",
  "passed": true,
  "evidence": {
    "process_alive_after_first_result": true,
    "second_message_produced_response": true,
    "first_result_at_ms": 2340,
    "second_response_at_ms": 4120
  },
  "notes": ["..."]
}
```

## 四、验证结果

**执行时间**：2026-05-29 15:10–15:12 | **执行环境**：WSL2 / claude CLI（OAuth）/ 模型默认

| # | 项目 | 状态 | 关键证据 |
|---|------|------|---------|
| V1 | stdin 持久监听 | ✅ PASS | 第一条 result 后 3 秒进程仍 alive；第二条 user message 后正常产生 "World！"。第一条 7.4s（含冷启动），第二条 2.7s（复用进程）→ 性能收益证实 |
| V2 | 对话记忆累积 | ✅ PASS | 第一条告知"张三丰"，第二条问"我叫什么"，CLI 回复"张三丰" |
| V3 | system-prompt 持久 | ✅ PASS | 5/5 全部命中 `[测试助手]` 前缀，无衰减 |
| V4 | 异常检测 | ⚠️ Partial | kill 后 returncode=-9，写入抛 `ConnectionResetError`（可检测）；但坏 JSONL `{not json}` 后 CLI 不退出、无 stderr（**静默吞掉**） |
| V5 | resume + stream-json | ✅ PASS | `--resume <key>` 不带 `--session-id` 可恢复对话历史（记得 Bob / BLUE42 / 绿色）。注意：resume 时不能同时传 `--session-id` |

### 完整证据（V1）
```json
{
  "first_result_received_ms": 7366,
  "first_assistant_text": "Hello！有什么需要帮忙的？",
  "alive_3s_after_first_result": true,
  "returncode_after_3s": null,
  "second_result_received_ms": 2701,
  "second_assistant_text": "World！"
}
```

### 完整证据（V2）
```json
{
  "first_assistant_text": "好的",
  "second_assistant_text": "张三丰。",
  "contains_name": true
}
```

### 完整证据（V3）
```
turn 1 "你好"           → [测试助手] 你好，小明，有什么需要帮忙？
turn 2 "今天天气怎么样"  → [测试助手] 我查不到实时天气，请用天气 App。
turn 3 "1 + 1 等于几"   → [测试助手] 2
turn 4 "推荐一本书"      → [测试助手]《人类简史》，宏观视角看人类发展。
turn 5 "再见"            → [测试助手] 再见，小明！
hit_rate: 5/5
```

**附带发现**：turn 1 回复包含「小明」—— CLI 自动加载了用户的 `~/.claude/CLAUDE.md`（含「用户的名字 小明」记忆）。这意味着我们的群聊 Agent CLI 会受用户全局 CLAUDE.md 污染。**待办**：Phase 1 实施时考虑 `--bare` 或显式覆盖工作目录。

### 完整证据（V4）
```json
{
  "kill_test": {
    "pid": 3140670,
    "alive_after_kill": false,
    "returncode_after_kill": -9,
    "write_after_kill_error": "ConnectionResetError",
    "kill_detected": true
  },
  "bad_jsonl_test": {
    "alive_after_bad_jsonl": true,
    "returncode": null,
    "bad_jsonl_handled": false
  }
}
```

## 五、Go/No-Go 决策矩阵

| V1 | V2 | V3 | V4 | 决策 |
|----|----|----|----|------|
| ❌ | * | * | * | **No-Go**：长驻方案不可行。回到 v2 messages 拆分（但 CLI 路径死结待解） |
| ✅ | ❌ | * | * | **No-Go**：长驻无对话累积优势，性价比不足 |
| ✅ | ✅ | ✅ | ✅ | **Go**：按 proposal §四 Phase 1 实施 |
| ✅ | ✅ | ⚠️ | * | **Go with caveat**：Phase 1 增加 reminder 注入策略 |
| ✅ | ✅ | ✅ | ❌ | **Go with caveat**：Phase 1 增加 watchdog + stdin write timeout |

## 六、运行须知

- 这些验证会消耗 Anthropic API token（每次验证约 4-10 次 LLM 调用）
- 建议用便宜模型：`ANTHROPIC_MODEL=claude-haiku-4-5-20251001` 或 mock 模式
- 必须在配置好 `ANTHROPIC_API_KEY` 或 OAuth 的环境跑
- 跑完后把 JSON 报告附在本文档 §四 表格的「证据」列

## 七、Phase 1 实施 caveat（来自验证发现）

V4 部分通过 + V3 附带发现，导出两个必须解决的工程约束：

### Caveat 1：坏 JSONL 静默吞掉 → JSONL 序列化必须类型化保证合法

**症状**：往 stdin 写 `{not json}\n` 后 CLI **不退出、不报错、stderr 无内容**。如果我们的 Pool 代码出 bug 写出非法 JSONL，用户消息会无声丢失。

**对策**：
- `ClaudeCodeProcessPool.send_user_message` 必须使用 Pydantic / dataclass 严格序列化，禁止手工字符串拼接
- 单元测试覆盖所有 JSONL 输出 schema
- 不依赖 CLI 的错误反馈作为可靠性来源

### Caveat 2：kill 检测可行但需要主动健康检查

**症状**：进程 SIGKILL 后写 stdin 抛 `ConnectionResetError`，**但只在写入时才感知**。如果 Agent 长时间不说话，进程崩了我们不知道。

**对策**：
- Pool v1 实现「写入前先 `proc.returncode is None` 检查」+ 失败时 lazy re-spawn
- Pool v2 引入心跳（每 N 分钟检查一次池中所有进程状态）
- 不需要专门 watchdog 协程（开销不划算）

### Caveat 3：用户全局 CLAUDE.md 污染 Agent 身份

**症状**：V3 中 turn 1 回复"你好，**小明**"——CLI 读取了用户 `~/.claude/CLAUDE.md` 中的「用户名字 小明」记忆，把它视为 Agent 自己应当遵守的知识。

**对策**（三选一，待 Phase 1 实施时决定）：
- A：spawn 时加 `--bare`（跳过 hooks/auto-memory/CLAUDE.md auto-discovery）— 最干净，但失去 CLI 的工具体系
- B：spawn 时 cwd 指向一个隔离的工作目录（无 CLAUDE.md）— 中等，但 ~/.claude/CLAUDE.md 仍会读
- C：在 system_prompt 顶部显式声明"忽略其他记忆中的身份信息，你的身份是 X" — 弱，可能与用户记忆冲突

**推荐 A**，理由：群聊 Agent 当前不需要 CLI 工具能力（不是写代码），`--bare` 反而提供更可控的隔离。

## 八、最终 Go/No-Go 决策

**Go**（带 §七 三个 caveat）。

按 proposal v3 §四 进入 Phase 1 实施前：
1. Phase 0 措辞修复必须先做（4 处小改 + 量化基线）
2. Phase 1 实施时必须落实 §七 三个 caveat
3. spec 文档同步（CLI-only 决策）作为并行任务进行
