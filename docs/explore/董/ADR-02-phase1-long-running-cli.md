# ADR-02：Phase 1 长驻 CLI + stream-json 改造

> 日期：2026-05-29 | 状态：**Accepted** | 上游：[ADR-01](./ADR-01-cli-first-pivot.md)

## 一、背景

### 1.1 Phase 0 验收结论

Phase 0 四处措辞修复后，固定场景 × N=20 量化基线结果：

| 指标 | 结果 | 判定 |
|------|------|------|
| 身份互串 | 0/60（0%） | 已解决 |
| 自己 @ 自己 | 0/60（0%） | 已消除 |
| 口吻传染 | — | 独立工单 |

身份互串率 <5%，Phase 0 措辞修复在单一场景下达标。

### 1.2 为什么还要做 Phase 1

Phase 0 修的是 prompt 层面（system_prompt 措辞），没有修结构层面。当前 `ClaudeCodeRuntime` 仍存在根本性问题：

1. **每次请求 spawn 新进程** — `create_subprocess_exec` → `stdin.write(prompt)` → `write_eof()` → 进程退出。Agent 没有"记忆"，所有对话历史靠 system_prompt 反复注入
2. **system_prompt 膨胀** — 随着群聊消息累积，delta 越长 system_prompt 越长，最终触及 token 上限。Phase 0 措辞能延缓但不能阻止
3. **冷启动开销** — V1 实测：首次 7.4s（含冷启动），后续如能复用进程仅 2.7s。当前每次 spawn 都付冷启动成本

Phase 0 的结论是"措辞修复够用"——在当前场景和当前对话长度下。但这不是永久方案。

### 1.3 Phase 0.5 全部通过

| 验证 | 结果 | 结论 |
|------|------|------|
| V1 stdin 持久监听 | ✅ | 长驻可行 |
| V2 对话记忆累积 | ✅ | CLI 自管历史 |
| V3 system_prompt 持久 | ✅ | 首次注入即可 |
| V4 异常检测 | ⚠️ | kill 可检测 |
| V5 resume + stream-json | ✅ | 崩溃恢复路径明确 |

技术假设全部验证通过，工程风险可控。

## 二、决策

### 决策：改造 ClaudeCodeRuntime 为长驻 + stream-json 模式

**当前（V0）**：
```
spawn → stdin.write(prompt) → write_eof() → read result → exit
```

**目标（Phase 1）**：
```
spawn（--input-format stream-json）→ 持续 stdin JSONL → 持续读 stdout → 长驻
```

对外 `AgentRuntime.stream()` 契约不变。内部从「短驻 + resume」切换为「长驻 + stream-json」。

### 灰度策略

通过环境变量 `CLAUDE_CODE_LONG_RUNNING=1` 切换，默认关。灰度期 V0 和 Phase 1 双路径共存，出问题一键回滚。

## 三、实施计划

### Step 1：最简长驻（核心改造）

| 项 | 内容 |
|----|------|
| 新增 `_ProcessHandle` | `proc` + `stdin_lock` + `session_key` + `last_used` |
| 进程缓存 | `_processes: dict[session_key, _ProcessHandle]`，初版永不淘汰 |
| 改 `_build_cmd` | 去 prompt 输入，加 `--input-format stream-json`，spawn 后 stdin 不关 |
| 改 `stream()` | 取/spawn handle → acquire lock → 写 user JSONL → 读到 `type=result` → release |
| 并发模型 | 同 `session_key` 串行（`asyncio.Lock`），不同 `session_key` 天然并发 |

暂不做：崩溃恢复、idle 淘汰、容量保护。

验收：同一 Agent 第二条消息不再 spawn；`phase0_baseline.py` 跑通。

### Step 2：崩溃恢复

- `stream()` 入口检测 handle 死亡（`returncode != None` 或 stdin closed）
- 死了 → `--resume <session_key>` 重连 → 当前请求 retry 一次
- 复用 V5 已验证：`--resume` + `--input-format stream-json` 可恢复历史

验收：`kill -9` 长驻进程后，下一条消息自动恢复。

### Step 3：生命周期 + 容量

- idle TTL 后台任务：超过 5 分钟未用 → `terminate()`
- FastAPI lifespan shutdown hook：关闭时清理所有子进程
- 全局上限默认 20，超出按 LRU 淘汰

验收：长跑 1 小时进程数稳定；shutdown 不留僵尸。

### Step 4：测试 + 灰度

- 单元测试：mock subprocess，覆盖锁 / 恢复 / 淘汰
- 性能对比：V0 vs Phase 1 跑 `phase0_baseline.py`，对比 spawn 次数和总耗时
- 保留 V0 路径：`CLAUDE_CODE_LONG_RUNNING=1` 切换

## 四、暂不做

| 项 | 原因 |
|----|------|
| `--include-partial-messages`（token 流式） | 等产品决策 |
| 跨 session 进程复用 | Step 3 LRU 已覆盖主要场景 |
| 协调者编排相关 | 协调者模块未完成，scope 外 |

## 五、风险与兜底

| 风险 | 兜底 |
|------|------|
| stdin 写入死锁（CLI 阻塞读） | 写入加 timeout，超时 kill 重连 |
| stream-json 事件 schema 与 V0 不同 | `_parse_line` 不变（V5 验证过事件结构一致） |
| 长驻进程内存泄漏 | Step 3 idle TTL 自然回收 |
| Step 1 无恢复机制，进程死 = session 卡 | 灰度 flag 默认关，主路径仍走 V0 |

## 六、影响文件

| 文件 | 操作 |
|------|------|
| `backend/app/infrastructure/llm/claude_code_runtime.py` | 重写 `stream()` + `_build_cmd()` |
| `backend/app/infrastructure/llm/claude_code_process_pool.py` | 新建（`_ProcessHandle` + 缓存 + TTL） |
| `backend/app/core/config.py` | 新增 `claude_code_long_running` 配置项 |
| `scripts/feasibility/phase0_baseline.py` | 性能对比基准 |
