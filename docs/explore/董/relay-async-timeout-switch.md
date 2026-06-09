# 群聊 Relay 阻塞问题 → 超时切换方案

## 问题

群聊 relay 会阻塞 HTTP 连接直到 Agent CLI 进程退出。短回复无影响（3-10s），但 Agent 如果调用了长时工具（如 Workflow），整个群聊会话被卡住直到超时（300s）。

### 触发场景

用户「写调研报告」→ Router 判 `relay` 给技术负责人 → 技术负责人 CLI 里跑 deep research Workflow → CLI 不退出 → HTTP 卡 300s → `Claude CLI 超时 (300s)`。

### 根因

1. **Router 分类不准**：`deepseek-chat` 把复杂任务判为 `relay` 而非 `task`（prompt 过度偏向 relay + 模型能力弱）
2. **relay 同步阻塞**：`_stream_one_agent()` 直接 spawn CLI 子进程，HTTP 同步等进程退出
3. **task 已不阻塞但从未被触发**：`_start_coordinator()` 已实现 fire-and-forget 后台执行，因 Router 从不判 task 而闲置

## 已做修复（路由层）

1. Router 模型 `deepseek-chat` → `deepseek-v4-pro`（`config.py:reactive_model`）
2. Router prompt 重构：两步决策树「先判类型，再选人」
   - task 明确触发条件：产出实质性成果 + ≥2 步骤 + 需协作
   - relay 选人不强制单人，跨领域可选多人
   - 典型示例显式标注（「写调研报告」→ task）
3. 涉及文件：`reactive_router.py:180-209`、`config.py:62`

## 方案对比

| | A：relay 全异步 | B：超时切换 ✅ | C：只修路由 |
|---|---|---|---|
| **做法** | relay 一律 spawn 后台立返 | 前 15s 流式，超时切后台 | 确保复杂任务被判 task |
| **流式体验** | ❌ 丢失 | 短回复保留，长任务告知 | 保留 |
| **前端改动** | 大 | 小（pending 状态） | 无 |
| **风险** | 体验降级 | 两套路径维护 | 依赖 Router 准确率 |

**选定 B**：兼顾流式体验和长任务不阻塞。

## 超时切换架构

```
CLI 进程 → adapter.stream() → asyncio.Queue
                                    │
            ┌───────────────────────┤
            ▼                       ▼
      HTTP 订阅者             后台收集者
      (最多 15s)             (一直跑到 CLI 退出)
            │                       │
       ┌────┴────┐           ┌─────┴─────┐
    正常完成    超时        独立落库    WS 推送
```

### 情况 1：Agent 在 15s 内回复完

```
CLI   ──text──text──text── DONE → 退出
Queue ──evt──evt──evt── sentinel
HTTP  ──chunk─chunk─chunk── 正常关闭
```
用户无感知，跟现在一模一样。

### 情况 2：Agent 超过 15s

```
CLI   ──text──text──text────text────text────text── DONE → 退出
Queue ──evt──evt──evt────evt────evt────evt── sentinel
                         │
HTTP  ──chunk─chunk─     │  ← 15s 到期
          "⏳ 正在后台处理..." 
          连接关闭
                         ↓
                    后台 asyncio.Task 继续读
                    → 读完拼完整回复
                    → session_factory() 独立落库
                    → ws_manager.broadcast() 推前端
```

## 关键实现点

| 层级 | 实现 |
|------|------|
| **Queue 解耦** | `adapter.stream()` 在后台 task 跑，events push 到 `asyncio.Queue(maxsize=200)`，HTTP 从同一 Queue 取 |
| **HTTP deadline** | `queue.get(timeout=remaining)`，remaining = 15s - 已用时间 |
| **后台落库** | 超时后 request-scoped DB session 失效 → 用 `session_factory()` 开独立 session（同 `post_system_background` 模式） |
| **WS 推送** | `ws_manager.broadcast(session_id, event)` → 前端无需轮询 |
| **CLI 不泄漏** | 后台 task 持有 adapter 引用，读完 DONE 正常退出 |
| **阈值 15s** | 覆盖 90%+ 正常回复（3-10s），超过的基本是重活 |

## 待实现

- [ ] `_stream_one_agent_with_timeout()` 方法
- [ ] relay 分支接入超时逻辑
- [ ] 前端：pending 状态 + WS 消息接收
