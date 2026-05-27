# 群聊讨论模式 — 业界方案调研

> 日期: 2026-05-25 | 来源: Web 搜索 AutoGen/CrewAI/Slack/OpenClaw/SlackAgents 等项目

## 一、上下文过时（Context Staleness）

**问题:** 多个 Agent 并发回复同一消息，快者先回、慢者基于旧上下文回复，产生矛盾或冗余。

| 方案 | 代表系统 | 机制 |
|------|----------|------|
| **回合制发言** | AutoGen GroupChat | GroupChatManager 每次只选一个 Agent 发言 → 广播给所有人 → 再选下一个。不存在并发回复，天然无过时问题 |
| 会话级串行队列 | OpenClaw | 同 session 内 `maxConcurrent=1`，全局队列控吞吐。debounceMs=1000 合并毫秒内到达的多条消息 |
| 结构化记忆 | Slack (InfoQ 2026.04) | 不用原始聊天记录，改用 Director's Journal + Critic's Review 结构化摘要，Agent 读到的是已整合的版本而非过期聊天 |
| 去抖合并 | OpenClaw | `debounceMs=1000`，毫秒内到达的多条消息合为一个 turn，避免并发触发 |

**关键取舍:** 串行队列保证一致性但牺牲并发吞吐；回合制无并发问题但延迟高。生产环境多用「会话级串行+全局并发」双层队列折中。

---

## 二、由谁回应（Who Should Respond）

**五种主流方案:**

| 方案 | 代表系统 | 机制 | 优点 | 缺点 |
|------|----------|------|------|------|
| **关键词/正则路由** | botinabox, Discord bot | 按优先级规则表匹配，兜底 LLM 路由 | 确定性强、可审计 | 规则维护成本高 |
| **LLM 动态选发言人** | AutoGen `speaker_selection="auto"` | Manager 用独立 LLM 调用评估上下文后选最合适的 Agent | 最灵活 | 额外 LLM 调用，结果不可预测 |
| **轮转制** | AutoGen `round_robin` | 固定顺序轮流发言 | 简单 | 机械，不区分消息相关性 |
| **@mention 定向** | SlackAgents, Hermes Agent | 用户显式 @Agent 名来指定 | 最可控 | 无法实现自主协作 |
| **置信度自选** | YES AND (CHI 2025) | 每个 Agent 自行计算对该消息的「有价值回应」置信度，高于阈值才发言 | 模拟人类"有话才说" | 校准难度高 |

**业界趋势:** 分层路由 — 先 @mention 定向，再关键词规则，最后 LLM 兜底。纯 LLM 决策在生产中不够稳定。

---

## 三、跨 Agent 感知与防循环

| 方案 | 代表系统 | 机制 | 防循环手段 | 可靠性 |
|------|----------|------|-----------|--------|
| **完全广播+终止条件** | AutoGen GroupChat | 所有回复广播给所有 Agent | `max_round` 硬限制 + 终止关键词("TERMINATE") + `allow_repeat_speaker=False` | MetaGPT/ChatDev 实测仍有 **60%-66% 失败率** |
| **任务委托隔离** | CrewAI | Agent 不读彼此原始聊天，通过结构化 Task 对象传递 | `allow_delegation=False` 阻止循环委托 | 安全但上下文缺失 |
| **去中心化 @ 协议** | SlackAgents (EMNLP 2025) | Agent 遇到不会的 → @同事 + 暂停自己(WAIT)，等回复后继续 | 模仿人类团队协作 | 避免中央协调器瓶颈 |
| **忽略 Bot 消息** | Discord 通用 | Bot 标记为 Bot 的消息被其他 Bot 忽略 | 粗暴但有效 | 简单场景够用 |

**防循环关键措施:**
- 忽略来自其他 Bot 的消息（Discord 通用做法）
- `parent_id` 追溯链 — 每个消息携带任务链 ID，同链不重复处理
- `max_iter` 硬限制（3-5 轮后强制终止）
- 角色约束（规划者只输出、执行者只执行，不交叉委托）

---

## 四、核心结论

三类问题并非独立：**回合制**天然解决前两个问题（无并发、无选择歧义），但吞吐受限；**串行队列+分层路由**是当前生产环境最成熟的折中方案；**置信度自选+结构化记忆**是 2025 年学术前沿方向，工程化尚早。

## 参考来源

- [AutoGen GroupChat Speaker Selection](https://microsoft.github.io/autogen/0.2/docs/tutorial/conversation-patterns/)
- [Slack Agent Context Management (InfoQ, 2026.04)](https://www.infoq.com/news/2026/04/slack-agent-context-management/)
- [OpenClaw Concurrency & Queue Architecture](https://www.cnblogs.com/zgq123456/articles/19701762)
- [Multi-Agent Group Chat Context & Thread Isolation](https://blog.gitcode.com/474f78118c71893013c7c1e9e33f6834.html)
- [botinabox Triage Routing Pattern](https://www.npmjs.com/package/botinabox)
- [SlackAgents Decentralized Protocol (EMNLP 2025)](https://aclanthology.org/2025.emnlp-demos.pdf)
- [Multi-Agent Failure Analysis: Inter-Agent Misalignment](https://ai.plainenglish.io/multi-agent-ai-systems-are-failing-heres-why-and-what-s-next-2cbc196ff58a)
- [YES AND Framework: Confidence-Based Turn-Taking (CHI 2025)](https://dl.acm.org/doi/10.1145/3706599.3720142)
- [Controlling AI Agent Participation in Group Conversations (CHI 2025)](https://ar5iv.labs.arxiv.org/html/2501.17258)
- [Microsoft Multi-Agent Reference Architecture: Short-Term Memory](https://microsoft.github.io/multi-agent-reference-architecture/docs/memory/Short-Term-Memory.html)
