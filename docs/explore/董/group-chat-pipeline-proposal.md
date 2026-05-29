# 群聊输入管道方案（v3）

> 日期：2026-05-29 | 状态：**Phase 0.5 V1-V5 全部完成；Phase 0 待启动；Phase 1 设计待修正**
> v3 修订：项目方向调整为 CLI-only，Phase 1 切换为长驻 + stream-json 模式
> v3.1 修订：两次场景推理暴露 8 处问题（3 简化错误 + 4 新要求 + 1 待验证假设），§1.4 fan-out 废弃
> 历史版本：v1（初稿，已废弃）→ v2（messages 时间交错，已被 v3 替代）
>
> **场景推理**：[场景推理.md](./场景推理.md) — 10 步压力测试覆盖正常路径 + 异常分支

## 验证结果速览（2026-05-29）

| 验证 | 结果 | 影响 |
|------|------|------|
| V1 stdin 持久监听 | ✅ | 长驻可行；第二条 user 响应 2.7s vs 首条 7.4s |
| V2 对话记忆累积 | ✅ | CLI 自管历史，IM 无需注入 self-history |
| V3 system_prompt 持久 | ✅ | 5/5 命中，首次 spawn 注入即可 |
| V4 异常检测 | ⚠️ | kill 可检测；坏 JSONL 静默吞掉 → caveat |
| V5 resume + stream-json 兼容 | ✅ | `--resume` + stream-json 可恢复历史；crash recovery 方案明确：spawn_resume() 不带 `--session-id`，直接用 `--resume <key>` |
| 附带发现 | ⚠️ | 全局 `~/.claude/CLAUDE.md` 污染 Agent 身份 → 需 `--bare` |

详见 [cli-streamjson-feasibility-test.md](../cli-streamjson-feasibility-test.md)。

## 一、问题（Problem）

### 1.1 业务问题：群聊身份错乱

详见 [group-chat-identity-issue-analysis.md](./group-chat-identity-issue-analysis.md)。四类根因：

| # | 根因 | 影响 |
|---|------|------|
| 1 | **身份窒息** — persona 一句话被几百字 delta 淹没 | 喵娘自称技术负责人 |
| 2 | **协调者泄漏** — _load_members 包含 coordinator_id | 成员列表多一个角色 |
| 3 | **默认 persona 太弱** — `f"你是 {name}。"` | 用户未填 system_prompt 时身份不稳 |
| 4 | **口吻传染** — 别人的猫娘口吻进入 delta 被模仿 | 技术负责人也说「喵～」 |

### 1.2 工程问题：CLI 路径的结构性矛盾

当前 `ClaudeCodeRuntime` 每次请求 spawn 子进程 + `--resume <key>`：

```python
# claude_code_runtime.py
async def stream(self, request):
    cmd = self._build_cmd(...)  # --resume <session_key> --system-prompt ...
    proc = await asyncio.create_subprocess_exec(*cmd, ...)
    proc.stdin.write(prompt.encode())  # 只送最后一条 user 内容
    proc.stdin.write_eof()
    # 进程退出
```

- delta / self-history 全压进 `system_prompt` → 身份窒息（根因 1）
- 想把 messages 拆开喂给 CLI：`_extract_prompt` 只支持取最后一条 user，**改造它会与 `--resume` 重放冲突**
- 想保留 SDK 路径作 messages 拆分参考：**SDK 路径本就要废弃（见决策 2）**

CLI 路径在「短驻 + resume」模式下无干净解法。

## 二、决策（Decision）

### 决策 1：Phase 0 措辞修复无条件先做

四处小改解决根因 2、部分覆盖 1 和 3。详见本文档 §四 Phase 0。

**任何长驻架构都不能替代措辞修复**，因为根因 1/4 的本质是 LLM 注意力机制，与进程模型无关。

### 决策 2：项目正式切换为 CLI-only

- 群聊主路径只走 `ClaudeCodeRuntime`（CLI）
- `ClaudeAdapter`（SDK 路径）**降级为测试/降级用**，不删除但不再投入演进
- `AgentSystem.ANTHROPIC_API` 枚举保留，新建 Agent 不推荐
- 影响文件：
  - `spec/architecture_架构定义.md` —「双轨」改「CLI 主，SDK 备」
  - `CLAUDE.md` 同步
  - 待办：单独 PR 完成 spec 文档同步（见 §五 待办）

### 决策 3：Phase 1 改为「长驻 + stream-json」

放弃 v2 的「ContextBuilder 内自实现 messages 时间交错 + 改 `_extract_prompt`」路线（CLI 路径死结）。

新路线：**ClaudeCodeRuntime 改造为长驻子进程，通过 `--input-format stream-json` 持续推送 JSONL user message，让 CLI 自己累积对话历史**。

参考实现：cc-haha 项目（`SessionRunner` + `replBridge`，详见 [cc-haha 上下文管理分析](../../../../mnt/d/Edge_files/cc-haha_context_management_analysis.md)，不在仓库内）。

### 决策 4：Phase 1 启动门槛 = Phase 0.5 验证通过 + Phase 0 量化基线达标

- **Phase 0.5（实测验证）**：4 个 CLI 行为假设，任一失败则 Phase 1 重新设计或弃用。详见 [cli-streamjson-feasibility-test.md](../cli-streamjson-feasibility-test.md)
- **Phase 0 量化基线**：如果 Phase 0 后身份互串率 <5%，Phase 1 推迟到下一阶段（避免过度工程）

### 决策 5：进程池分阶段渐进

不在 Phase 1 一次性建完整进程池。三阶段：

| 阶段 | 形态 | 触发条件 |
|------|------|---------|
| v1（最小可用）| 每 `(session_id, agent_id)` 首次说话时 spawn，session 关闭或服务重启时退出。无池。 | Phase 1 必做 |
| v2（防泄漏）| 引入 idle timeout（如 30 分钟无活动自动关闭） | 监控发现进程数累积时 |
| v3（规模化）| LRU 驱逐 + 心跳 + 失败重启 | 单实例 >50 长驻进程时 |

### 决策 6：记忆系统作为后续参考归档，不进当前 PRD

cc-haha 的 frontmatter + AI 检索 + 团队记忆设计，记入 [memory-system-future.md](./memory-system-future.md)，作为「未来引入 Agent 长期记忆时的起点」，不影响本方案。

## 三、根因 vs 方案覆盖矩阵

| 根因 | Phase 0 | Phase 1（长驻 + stream-json） |
|------|---------|------------------------------|
| 1. 身份窒息 | ⚠️ 措辞强化 | ⚠️ stream-json 每条 user 独立 message，注意力边界更清晰；但累积长度变长后仍会衰减 |
| 2. 协调者泄漏 | ✅ 1 行修复 | — |
| 3. 默认 persona 弱 | ⚠️ 模板强化，用户填了 system_prompt 时不覆盖 | — |
| 4. 口吻传染 | ❌ 不解决 | ❌ 不解决 |

口吻传染（根因 4）需要独立工单。

## 四、实施阶段

### Phase 0：措辞修复（无条件先做，1 个 PR）

| # | 文件 | 改动 |
|---|------|------|
| P0-1 | `context_builder.py:98` | persona 默认值改为强化模板（含否定式约束） |
| P0-2 | `prompt_templates.py:15` | `GROUP_CHAT_CONTRACT` 第 1 条改为身份确认规则 |
| P0-3 | `context_builder.py:213` | `_load_members` 排除 `coordinator_id` |
| P0-4 | `prompt_templates.py:51` | `format_delta` 顶部加发言人前缀说明 |

#### 量化基线

固定 fixture（3 Agent × 固定 trigger × 固定 seed × N=20），统计：
- 身份互串次数
- 自己 @ 自己次数
- 口吻传染次数（不期望本阶段下降）

### Phase 0.5：CLI 长驻可行性实测（**Phase 1 的 go/no-go 门槛**）

详见 [cli-streamjson-feasibility-test.md](../cli-streamjson-feasibility-test.md)。5 个验证项（V5 为场景推理后新增）：

| # | 验证 | 失败后果 |
|---|------|---------|
| V1 | `--print --input-format stream-json` 推送多条 JSONL 后进程不退出 | 长驻方案不可行，回到 v2 messages 拆分 |
| V2 | 同一 `--session-id` 长驻内消息累积 | 需切换到内部 conversation 状态 |
| V3 | `--system-prompt` 在多轮后仍生效 | 需附加 reminder 注入策略 |
| V4 | 异常退出的检测机制 | 需 watchdog |
| V5 | `--resume <key> --input-format stream-json` 崩溃恢复兼容性 | 需"补灌历史"机制（见 N2） |

### Phase 1：长驻 + stream-json（仅在 Phase 0.5 通过 + Phase 0 量化不达标时启动）

#### 1.1 ContextBuilder 大幅简化

```python
# context_builder.py:_build_group 改造后
async def _build_group(self, *, session, group, target_agent, trigger):
    persona = target_agent.system_prompt or DEFAULT_PERSONA_TEMPLATE.format(...)
    members = await self._load_members(group)  # 排除 coordinator（P0 已修）
    members_block = format_members(members, target_agent)
    
    system_prompt = "\n\n---\n\n".join([
        f"[身份]\n{persona}",
        f"[行为约定]\n{GROUP_CHAT_CONTRACT}",
        f"[群成员]\n{members_block}",
    ])
    return AgentRequest(
        messages=[{"role": "user", "content": trigger.content}],  # 仅本轮 trigger
        system_prompt=system_prompt,  # 仅首次 spawn 时通过 --system-prompt 注入
        ...
    )
```

> **已知简化**：trigger_text 将多条 delta 消息拼接为一条 user message
> 推送（`"老张: ...\n用户: ...\n小李: ..."`），未利用 stream-json 的逐条消息边界。
> 这等价于告诉 CLI"有一个人同时说了三句话"。当前阶段接受此简化（每条 delta
> 消息单独推送会触发多次 assistant 回复），后续可探索 stream-json 的
> multi-message 模式是否支持批量 user 推送后单次回复。

废弃：`_compute_delta`、`_maybe_truncate`、watermark 相关逻辑、L1 记忆 window 注入。**CLI 自己管历史**。

#### 1.2 新建 `claude_code_process_pool.py`

职责：
- 维护 `(session_id, agent_id) → SubprocessHandle` 映射
- `get_or_spawn(key, system_prompt)`：首次 spawn 用 `--system-prompt`，后续复用
- `send_user_message(key, content)`：往 stdin 推送 stream-json user message
- `read_until_result(key)`：流式读 stdout 直到 result 事件
- `terminate_all()`：服务关闭时清理

v1 不实现：idle timeout、LRU、心跳。

#### 1.3 `claude_code_runtime.py` 改造

```python
class ClaudeCodeRuntime:
    def __init__(self, pool: ClaudeCodeProcessPool, ...):
        self._pool = pool
    
    async def stream(self, request):
        key = compute_session_key(request)
        await self._pool.get_or_spawn(key, system_prompt=request.system_prompt)
        await self._pool.send_user_message(key, request.messages[-1]["content"])
        async for line in self._pool.read_until_result(key):
            yield parse_event(line)
        # 进程不退出
```

`_build_cmd` 改为：
```python
cmd = [
    "claude", "--print",
    "--input-format", "stream-json",
    "--output-format", "stream-json",
    "--verbose", "--include-partial-messages",
    "--session-id", session_key,  # 或 --resume
    "--system-prompt", system_prompt,
    "--permission-mode", self._permission_mode,
    "--max-turns", str(self._max_turns),
]
```

#### 1.4 ~~新增 application 层：fan-out 广播~~（已废弃）

> **废弃原因（场景推理 T5 确认）**：stream-json 协议不支持"只读推送"——每条 user message
> 都会触发 CLI 生成 assistant 回复。fan-out 会导致所有活跃 Agent 同时抢答，破坏协调者
> 的发言顺序控制。
>
> **正确设计**：纯 pull 模式。Agent 只在被协调者选中发言时，通过 watermark delta 感知
> 群里的新消息。沉默 Agent 不感知群里变化，直到下次被触发 — 这是 pull 模式的固有特性，
> 不是 bug（见 N4）。

<details>
<summary>原 fan-out 代码（保留作设计记录）</summary>

```python
# discussion_orchestrator.py 新增（已废弃）
async def fanout_to_listeners(self, message, group, exclude_agent_id, pool):
    for agent_id in group.member_ids:
        if agent_id == exclude_agent_id:
            continue
        if not pool.has(session.id, agent_id):
            continue
        speaker_name = self._name_resolver.resolve(message.sender_agent_id)
        await pool.send_user_message(
            (session.id, agent_id),
            f"{speaker_name}: {message.content}",
        )
```

</details>

#### 1.5 影响文件清单

| 文件 | 操作 |
|------|------|
| `claude_code_runtime.py` | 重写 |
| `claude_code_process_pool.py` | 新建 |
| `context_builder.py:_build_group` | 大幅简化 |
| `context_builder.py:_compute_delta` | 废弃 |
| `context_builder.py:_load_members` | P0 已改 |
| `discussion_orchestrator.py` | ~~新增 fanout 逻辑~~（已废弃，改纯 pull） |
| `chat_service.py` | ~~同步 fanout 调用~~（已废弃） |
| `prompt_templates.py:format_delta` | 废弃（不再需要 delta 渲染） |
| `watermark_store.py` | 仍保留（私聊未必废弃），群聊路径不再使用 |
| `factory.py` | Runtime 注入 pool 依赖 |
| `main.py` / app lifespan | 启动时创建 pool，关闭时 terminate_all |

## 五、场景推理发现（v3.1 修正）

> 详见 [场景推理.md](./场景推理.md) — 10 步支付功能评审场景，覆盖首次 spawn、复用、用户插话、崩溃恢复。

### 5.1 简化错误（3 处，已修正）

| # | 错误 | 修正 |
|---|------|------|
| S1 | §1.4 fan-out 广播 | 废弃。stream-json 协议无"只读推送"，每条 user message 触发回复。改为纯 pull。 |
| S2 | trigger_text 多条 delta 拼为一条 user message | 已知简化，§1.1 已标注。后续探索 stream-json 多消息推送。 |
| S3 | fan-out 影响文件（chat_service / discussion_orchestrator） | §1.5 已标注废弃 |

### 5.2 新设计要求（4 处，必须补入 Phase 1）

| # | 要求 | 详情 | 影响 |
|---|------|------|------|
| **N1** | Watermark commit 语义 | CLI spawn 成功 ≠ 发言成功。watermark 只能在 `read_until_result` 成功完成后推进。spawn 失败 / read 超时 / 输出错误 都不推进。 | `watermark_store.py` + `discussion_orchestrator.py` |
| **N2** | 崩溃恢复策略 | ✅ V5 已验证：`--resume <key>` + `--input-format stream-json` 兼容。注意点：resume spawn 不能同时传 `--session-id`（CLI 会报错要求加 `--fork-session`），直接用 `--resume <key>` 即可。 | `claude_code_process_pool.py`（新增 `spawn_resume` 路径） |
| **N3** | `[轮到你发言]` 标记误读风险 | 控制指令塞进 user message body，LLM 可能复读/误解。首次实测时关注前 5 次回复是否出现复读，必要时改用 system reminder。 | trigger_text 格式 |
| **N4** | 沉默 Agent 不感知群变化 | pull 模式固有特性：Agent 不被选中就不拉 delta。不是 bug，但需文档明确。 | 文档 |

### 5.3 待验证假设

| # | 假设 | 验证方式 | 阻塞 |
|---|------|---------|------|
| V5 | `--resume <key> --input-format stream-json` 可恢复历史 | ✅ 已验证通过 — 写脚本 spawn → 推送 → kill → `--resume` 重连 → 推送 → CLI 记住了之前的 turn | Phase 1 crash recovery 策略 |

## 六、待办（Open Questions / TODO）

### 必须在 Phase 1 开始前回答

| # | 待办 | 状态 / 责任 |
|---|------|------------|
| Q1 | 跑 Phase 0.5 的验证脚本 | ✅ V1/V2/V3/V5 PASS, V4 Partial，见 [feasibility-test 文档](../cli-streamjson-feasibility-test.md) |
| Q2 | Phase 0 量化基线脚本（固定 fixture × N=20）| ⏳ 待做（Phase 0 验收的前置） |
| Q3 | `--system-prompt` 在长驻进程中是否每次推送都重申？还是仅首次有效？ | ✅ V3 已回答：首次注入即可，5/5 全部生效 |
| Q4 | 长驻 CLI 进程的 stderr/异常退出如何被 IM 层感知？ | ✅ V4 已回答：写入时抛 ConnectionResetError，但需 write 前主动检查 returncode |
| Q10 | 隔离用户全局 `~/.claude/CLAUDE.md` 污染（V3 附带发现） | ⏳ Phase 1 决策：`--bare` vs 工作目录隔离 vs prompt 覆盖（推荐 `--bare`） |
| Q11 | JSONL 序列化层的类型化保证（V4 caveat） | ⏳ Phase 1 实施时落实（Pydantic / dataclass） |
| Q12 | V5：`--resume` + `--input-format stream-json` 崩溃恢复兼容性 | ✅ 已通过 — `--resume <key>` 不带 `--session-id` 即可恢复历史（见 [V5 脚本](../../scripts/feasibility/v5_resume_recovery.py)） |

### 设计期待解

| # | 待办 | 影响 |
|---|------|------|
| Q5 | 当 Agent 离群、群解散时，对应的 CLI 进程是否立即终止？还是等 session 关闭？ | Pool 生命周期 |
| Q6 | 同一 Agent 在多个群里（未来场景），是否每个群独立 CLI 进程？ | uuid5(session_id, agent_id) 当前已隔离，应继续 |
| Q7 | 服务重启后，长驻进程全部丢失，--resume 能否完整恢复历史？还是要附加 replay？ | 重启恢复策略 |
| Q8 | 私聊场景是否也切长驻？还是保留当前「短驻 + resume」？ | 范围决策 |
| Q9 | 口吻传染（根因 4）的独立工单方向：是 delta 渲染剥离 persona 标记，还是 contract 显式禁止模仿？ | 单独工单 |

### Spec 同步待办

| # | 待办 |
|---|------|
| S1 | `spec/architecture_架构定义.md` 「双轨」改「CLI 主，SDK 备」 |
| S2 | `CLAUDE.md` 同步 CLI-only 决策 |
| S3 | `spec/roadmap_开发路线图.md` 新增 Phase 0 / Phase 0.5 / Phase 1 任务 |
| S4 | `docs/adapter-cli-flow_适配器CLI流程分析.md` 更新长驻模式调用链 |

### 文档归档

| # | 文件 |
|---|------|
| D1 | 本方案 v3 取代 v2，v2 内容仅在 EVOLUTION 中保留决策记录 |
| D2 | [memory-system-future.md](./memory-system-future.md) — cc-haha 记忆系统作为后续参考 |
| D3 | EVOLUTION.md 新增今天的决策条目 |

## 六、风险与边界

1. **stream-json 长驻能力** — Phase 0.5 V1-V5 全部通过。V5 证实 crash recovery 可行
2. **进程池资源管理** — v1 无 idle timeout，长跑后可能内存膨胀，需要监控阈值告警
3. **崩溃恢复** — proc 崩溃后 `--resume <key>` 可恢复历史（V5 已通过）。注意：resume spawn 不能同时传 `--session-id`，直接用 `--resume <key>`
4. **`--resume` 与首次 spawn 的语义边界** — 首次必须用 `--session-id` 新建，后续才能 `--resume`。Pool 必须区分两种状态
5. **测试基础设施** — Phase 0/1 都依赖量化基线脚本，需先建好（固定 seed + 自动化场景重放）
6. **pull 模式信息延迟** — 沉默 Agent 不感知群变化（N4），不是 bug 但可能导致 Agent 决策时缺乏完整上下文
