# Agent Memory 外部调研综合报告

> 日期：2026-06-02 | 方法：3 路并行 agent 调研（GitHub 项目 + 学术论文 + 生产系统）
> 与前续文档关系：补全 `ref-memory-comparison.md` 和 `evercore_quality_assurance_analysis.md` 未覆盖的最新进展

---

## 一、核心发现（TL;DR）

### 1.1 三代技术演进

| 代际 | 时间 | 代表 | 思路 | LoCoMo 得分 |
|------|------|------|------|-------------|
| **第一代** | 2023-2024 | Mem0, Motorhead | "RAG 太难了，封装成简单 API" | 60-70% |
| **第二代** | 2024-2025H1 | Zep, Memobase, Cognee | "相似≠相关"，加知识图谱+时间轴 | ~75% |
| **第三代** | 2025H2-2026 | EverMemOS, Supermemory ASMR, A-Mem | "它不是数据库，是大脑/OS" | 85-99%+ |

### 1.2 三个与你直接相关的结论

1. **向量检索单独不够** — MemBench 实测：最强 embedding 模型也只有 ~62% 检索准确率。必须混合检索（dense + sparse + rerank）。
2. **PG + pgvector 对 B1 规模完全够用** — 10M 向量以内 pgvector 性能无瓶颈，你的项目已确认 Phase B1 不需要向量检索。
3. **不要低估"简单方案"** — Letta 实验表明 grep + markdown（74%）反超专用图工具（68.5%）；ConvoMem 基准（75K QA 对）证明 <150 轮对话时全上下文优于 RAG 记忆。

---

## 二、GitHub 高星项目深度对比

### 2.1 顶级项目速览（>10K stars）

| 项目 | Stars | 核心技术 | 存储 | 检索方式 | 关键指标 |
|------|-------|---------|------|---------|---------|
| **Mem0** | 55.6K | 混合向量+图谱+KV | 可插拔(10+向量库) | 语义相似度 | LoCoMo 91.6%（2026新算法）/ 64.7%（旧版） |
| **Claude-Mem** | 36K | Claude Code 专用 | SQLite FTS5 + Chroma | 自动工具调用捕获 | — |
| **Zep/Graphiti** | 25.9K | 时序知识图谱 | 自研图引擎 | Cos+BM25+BFS+RRF+MMR | DMR 94.8-98.2% |
| **Letta/MemGPT** | 22.9K | OS 范式虚拟内存 | pgvector/Aurora | Agent 工具调用自主检索 | LoCoMo 74% |
| **Supermemory** | 22.6K | ASMR 多Agent推理 | **无向量库** | 6 Agent 并行推理 | LongMemEval **99%** |
| **MemU** | 13.6K | 记忆即文件系统 | PG+pgvector | 自主记忆Agent | LoCoMo 92%（官方，外验差异大） |
| **Cognee** | 12.9K | ECL 管线+知识图谱 | LanceDB+Kuzu/Neo4j | 图谱遍历+向量+时间 | 图增强后 ~90%（自称） |
| **ENGRAM** | 3.6K | Go 单二进制 | SQLite+FTS5 | 渐进式披露 | 零运行时依赖 |

### 2.2 对你最有参考价值的三个

#### Supermemory ASMR（2026.03）— **反向量数据库路线**

**最激进的发现**：完全放弃向量数据库，用 3 个 Observer Agent + 3 个 Searcher Agent 的并行推理管线，在 LongMemEval 达到 **99%**。

```
传统路线：User Query → Embedding → Vector Search → Rerank → Top-K
ASMR 路线：User Query → 3 Observer Agents（并行分析记忆） 
                     + 3 Searcher Agents（并行搜索） 
                     → Consensus → Best Match
```

启示：对于你的项目，如果记忆量 < 50 条（B1 阶段），Agent 自主 `grep` + 阅读比向量检索更准确。

#### EverMemOS（盛大陈天桥团队）— **LoCoMo 最高验证分 92.3%**

4 层生物启发式记忆：Sensory → Working → Episodic → Semantic，底层 Milvus + ES + MongoDB + Redis。首个在少于全上下文 tokens 的情况下超越全上下文基线的系统。

你们已深入分析过它的 EverMem 插件侧（`evercore_quality_assurance_analysis.md`），不需要重复。

#### A-Mem（NeurIPS 2025）— **写入时建立链接**

Zettelkasten 风格：在写入记忆时就建立与已有记忆的链接（而非常规 RAG 的检索时匹配）。多跳推理 F1 提升 ~2 倍，tokens 减少 85-93%。

```
常规 RAG：写入时只存内容 → 检索时临时匹配
A-Mem：    写入时分析关系 → 建立链接 → 检索时沿链接追溯
```

这对你的 `[MEMORY:]` 标记写入路径有直接参考价值——Agent 写入时可以同时指定与哪些已有记忆关联。

---

## 三、学术论文关键发现

### 3.1 必读论文（按与你项目相关度排序）

| 优先级 | 论文 | 年份/会议 | 一句话 | 对你的价值 |
|--------|------|----------|--------|-----------|
| ⭐⭐⭐⭐⭐ | **Generative Agents** (Park et al.) | 2023/UIST | Memory Stream：recency×importance×relevance 三因子检索 + Reflection 反思 | 记忆检索的评分公式可直接借鉴 |
| ⭐⭐⭐⭐⭐ | **CoALA** (Sumers et al.) | 2023/TMLR | 记忆分 working/episodic/semantic/procedural 四种，定义 action space 和 decision loop | 记忆分类的理论基础，LangChain 已采用 |
| ⭐⭐⭐⭐⭐ | **MemGPT** (Packer et al.) | 2023/arXiv | OS 范式：主上下文(RAM) + 外部上下文(磁盘) + LLM 自主管理分页 | Letta 的理论基础，自管理记忆 |
| ⭐⭐⭐⭐ | **HippoRAG** (Gutierrez et al.) | 2024/NeurIPS | KG 作 hippocampal index + Personalized PageRank 检索，10-30x 比迭代检索便宜 | 如果未来做 KG 增强，这是最佳参考 |
| ⭐⭐⭐⭐ | **LongMemEval** (Wu et al.) | 2025/ICLR | 500 题/5 种记忆能力的标准评测基准 | 测试集设计的参考标准 |
| ⭐⭐⭐⭐ | **RecMem** | 2026/ACL | 只在持续复现时才触发 LLM 摘要，token 消耗降低 87% | Phase C 被动提取的成本优化方案 |
| ⭐⭐⭐ | **SleepGate** | 2026/arXiv | 睡眠启发三阶段遗忘：突触下调→选择性重放→定向遗忘，97-99.5% 准确率 | 如果记忆量膨胀，遗忘策略参考 |
| ⭐⭐⭐ | **RAPTOR** (Stanford) | 2024/ICLR | 层次化摘要树：chunk→embed→cluster→summarize 递归，多粒度检索 | 记忆编译 Phase C 的实现参考 |

### 3.2 关键数据点

- **最强 embedding 模型也才 62% 检索准确率**（MemBench，OpenAI text-embedding-3-large）→ 纯向量检索不可靠
- **ConvoMem（75K QA 对）的核心结论**：<150 轮对话时，全上下文（70-82%）优于 RAG 记忆（30-45%）。RAG 记忆只在超过 150 轮对话后才必要
- **11 个主流 embedding 模型彼此差距 <3%**（Agentset 2025.11 研究）→ 选 embedding 不如关注成本/延迟/部署
- **Letta 实验**：grep + markdown（74%）> 专用图工具（68.5%）→ Agent 能力比检索机制更重要

---

## 四、生产系统技术选型

### 4.1 向量数据库对比（针对 Agent Memory 场景）

| 数据库 | p95 延迟(10M) | 混合检索 | 多租户 | 自托管成本 | 推荐场景 |
|--------|--------------|---------|--------|-----------|---------|
| **pgvector** | ~50ms | FTS 扩展 | Schema | 免费（已有 PG） | **你的 B1→B2 首选** |
| **Qdrant** | ~22ms | 原生 | Collections | 免费 | 性能优先+自托管 |
| **Weaviate** | ~35ms | **原生 BM25** | 原生租户 | 免费 | 需要原生混合检索 |
| **Milvus** | ~50ms | 标量过滤 | Partitions | 免费 | >100M 向量 |
| **ChromaDB** | N/A | 基础 | Collections | 免费 | 原型验证 |
| **Pinecone** | ~45ms | SPLADE | Namespaces | $70-140/月(1M) | 零运维 |

**对你的建议**：Phase B1 不需要向量库（已决策）。B2 加 `tsvector` 全文索引（PG 原生，零新增基础设施）。Phase C 要上向量检索时，pgvector 是自然选择——已在 PG 栈内，10M 以内无性能瓶颈。

### 4.2 Embedding 模型选择

| 模型 | MemBench Avg@10 | MTEB | 维度 | 许可 | 推荐场景 |
|------|----------------|------|------|------|---------|
| OpenAI text-embedding-3-large | **61.85%** | ~64 | 3072 | 商业 API | 质量优先+可接受 API 成本 |
| BGE-M3 (BAAI) | 52.93% | ~67 | 1024 | **MIT** | 自托管首选，支持 dense+sparse+ColBERT |
| Cohere Embed v3 | — | ~65 | 1024 | 商业 API | 多语言+Rerank 生态 |
| E5-mistral-7b | — | ~66 | 4096 | MIT | 长上下文(32K) |

**对你的建议**：Phase C 上向量检索时，自托管选 BGE-M3（MIT 许可，一个模型支持 dense/sparse/ColBERT 三种检索），API 选 OpenAI text-embedding-3-large。

### 4.3 Reranking 策略

| 策略 | 速度 | 准确度 | 成本 | 推荐 |
|------|------|--------|------|------|
| 无交互(embedding) | 最快 | 最低 | 1x | 做初筛 |
| 后交互(ColBERT) | 中 | 好 | 中 | 速度-准确平衡 |
| 前交互(Cross-encoder) | 慢 | **最高** | ~5000x | Top-20→Top-5 |
| LLM-as-reranker | 最慢 | 高 | 高 | 复杂场景 |

**最佳实践**：向量检索 Top-20 → Cross-encoder Rerank 到 Top-5 → 注入 LLM。

---

## 五、基准测试全景

### 5.1 主要基准

| 基准 | 规模 | 评测维度 | 关键发现 |
|------|------|---------|---------|
| **LongMemEval** (ICLR 2025) | 500 题，~115K tokens/题 | 提取、多会话推理、知识更新、时间、弃权 | 商业系统在持续交互中准确率下降 30% |
| **LoCoMo** (ACL 2024) | 35 会话，300 轮，7.5K QA | 单跳、多跳、时间、开放域、对抗 | 最广泛采用的记忆基准 |
| **ConvoMem** (2025) | **75,336 QA 对** | 6 类 | <150 轮时全上下文优于 RAG 记忆 |
| **DMR** (Zep, 2025) | 深度记忆检索 | 多步研究检索 | Zep 94.8-98.2% |
| **Memora** (ACL 2026) | 引入 FAMA 指标 | 惩罚不遗忘过时信息 | 遗忘是功能不是 bug |

### 5.2 性能排行榜

| 系统 | LoCoMo | LongMemEval | 方法特征 |
|------|--------|-------------|---------|
| Supermemory ASMR | — | **99%** | 多Agent并行推理，无向量库 |
| EverMemOS | **92.3%** | 82% | 4层生物启发 |
| Mem0 (新算法) | 91.6% | 94.8% | 混合向量+图谱 |
| Letta | 74.0% | — | OS文件系统范式 |
| Memobase | ~74-75% | — | 用户Profile导向 |

### 5.3 评测指标速查

| 指标 | 关注什么 | 适用场景 |
|------|---------|---------|
| Recall@K | 有没有漏掉 | 不能遗漏任何相关记忆 |
| Precision@K | 有没有噪声 | 注入 token 预算紧张 |
| MRR | 第一条对不对 | 只需最佳匹配 |
| NDCG@K | 排序好不好 | 多条记忆按相关度排列 |

**诊断技巧**：Recall@20 高但 MRR@5 低 → 检索能召回但排序不行 → 加 Reranking。

---

## 六、对 AgentHub 项目的具体建议

### 6.1 检索策略分级演进（结合已有路线图）

```
Phase B1（当前）: ORDER BY updated_at DESC + memory_type 过滤
  └─ 记忆量 < 50 条/Agent，够用
  
Phase B2: + tsvector 全文索引（PG 原生）
  └─ 关键词匹配，零新增基础设施
  └─ 参考：生成式检索的三因子公式
      score = recency × 0.3 + importance × 0.2 + keyword_match × 0.5

Phase C: + pgvector 向量检索 + 混合检索
  └─ Embedding: BGE-M3（自托管，MIT）
  └─ 检索: vector Top-20 → cross-encoder rerank → Top-5
  └─ 混合: dense(0.5) + sparse/BM25(0.3) + recency(0.2)
```

### 6.2 记忆检索评分公式（可立即采用）

参考 Generative Agents（Park et al. 2023）的三因子公式，适配 B1：

```python
def memory_score(memory, query, now):
    recency = exponential_decay(
        hours_ago=(now - memory.updated_at).total_hours(),
        half_life=24 * 7,  # 一周半衰期
    )
    importance = memory.metadata.get("importance", 0.5)
    relevance = keyword_match_score(query, memory.title + " " + memory.content)
    
    return (
        0.3 * recency +
        0.2 * importance +
        0.5 * relevance
    )
```

### 6.3 检索准确度提升的四个杠杆

按投入产出比排序：

1. **Reranking**（最大提升，中等成本）— 粗筛 Top-20 → 精排 Top-5
2. **混合检索**（大提升，低成本）— 关键词 + 语义，互补覆盖
3. **查询改写**（中等提升，低成本）— 用户消息 → LLM 扩展为多个检索查询（参考 HiMeS 的 RL 训练查询改写器）
4. **更好的 embedding**（边际提升，中等成本）— 见 §4.2，模型间差异 <3%

### 6.4 特别提醒

1. **不要过早优化检索引擎** — ConvoMem 的 75K QA 对数据证明：记忆量 < 150 条时，简单方案和复杂方案差距不大，Agent 自身能力比检索机制更重要。

2. **遗忘和检索同等重要** — SleepGate、RecMem、LUFY 一致证明：选择性遗忘比存所有东西效果好。你的 Append-Only + 检索时过滤策略（方向 B §10.3）方向正确。

3. **Agent 自主检索 > 固定检索管线** — Letta 的核心洞察：让 Agent 自己决定搜什么、读什么，比预设的检索 pipeline 更准确。

4. **Profile 导向 vs 对话搜索导向** — Memobase（面向用户画像）和 Mem0（面向对话搜索）走了两条路。你的场景是 Agent 协作记忆，两者都需要——Agent 的"人格/能力 facts"（profile 导向）+ "项目决策/经验"（对话搜索导向）。

---

## 七、参考资源汇总

### 论文（按优先级）
- [Generative Agents](https://arxiv.org/abs/2304.03442) — Park et al., UIST 2023
- [CoALA](https://arxiv.org/abs/2309.02427) — Sumers et al., TMLR 2023
- [MemGPT](https://arxiv.org/abs/2310.08560) — Packer et al., 2023
- [HippoRAG](https://arxiv.org/abs/2405.14831) — Gutierrez et al., NeurIPS 2024
- [LongMemEval](https://arxiv.org/abs/2410.10813) — Wu et al., ICLR 2025
- [LoCoMo](https://arxiv.org/abs/2402.17753) — Maharana et al., ACL 2024
- [RecMem](https://arxiv.org/abs/2605.16045) — ACL 2026 Findings
- [SleepGate](https://arxiv.org/abs/2603.14517) — 2026
- [RAPTOR](https://arxiv.org/abs/2401.18059) — Sarthi et al., ICLR 2024
- [A-Mem](https://github.com/WujiangXu/A-mem) — NeurIPS 2025

### 项目
- [Mem0](https://github.com/mem0ai/mem0) — 55.6K stars
- [Letta](https://github.com/letta-ai/letta) — 22.9K stars
- [Zep/Graphiti](https://github.com/getzep/graphiti) — 25.9K stars
- [Supermemory](https://github.com/supermemoryai/supermemory) — 22.6K stars
- [Cognee](https://github.com/topoteretes/cognee) — 12.9K stars
- [ENGRAM](https://github.com/rawcontext/engram) — 3.6K stars

### 基准
- [EverMemBench](https://arxiv.org/pdf/2602.01313) — 评测框架
- [MemoryBench](https://github.com/supermemoryai/memorybench) — Supermemory 的评测框架
- [LongMemEval 数据集](https://huggingface.co/datasets/xiaowu0162/longmemeval-s-dataset)

---

---

## 附录 A：AI HOT 最新动态（2026.05.27-06.02，最近 7 天）

> 数据来源：aihot.virxact.com，API `mode=all&q=memory` + `q=agent&category=paper`
> 以下为与 Agent 记忆直接相关的条目，按发布时间倒序

### A.1 产品与框架发布

| 条目 | 来源 | 日期 | 要点 |
|------|------|------|------|
| **Memory OS** — 6 层开源记忆栈 | MarkTechPost | 06-01 | 构建在 Hermes Agent 之上，含门控检索机制 + wiki 系统，本地持久记忆 |
| **腾讯混元 Hy-Memory** — Agent 长期记忆插件 | 腾讯混元 / IT之家 | 06-01 / 05-28 | 专为 OpenClaw 设计，6 层记忆框架 + System1/System2 双系统 + 三层进化链，定位"Agent 的第二大脑" |
| **FluxMem** — 记忆作为动态演化图拓扑 | DAIR.AI / arxiv | 05-28 | 三阶段并行：初始连接形成 → 反馈驱动精炼 → 长期巩固为可复用程序性记忆 |

### A.2 学术论文

| 论文 | 日期 | 核心发现 |
|------|------|---------|
| **JAMEL** — 通过新颖性信号联合训练记忆与探索 | 06-01 | 用代码覆盖率等确定性新颖性信号训练记忆模块，无需人工标注 |
| **DecMem** — 解耦记忆架构 | 05-29 | 可学习、可扩展的记忆架构，解决长时程视频世界模型的一致性问题 |
| **TaskMem** — 面向任务的多模态记忆策略学习 | 05-29 | 基于强化学习的记忆策略，两阶段训练：先学"记什么"，部署后持续优化 |
| **MemTrace** — 记忆系统错误追踪与归因 | 05-27 | 将记忆管线转为可执行记忆演化图，构建 MemTraceBench 基准 |
| **MEMO** — 无需修改 LLM 参数的专用记忆模型 | 05-27 | 将新知识编码到独立可训练的 MEMORY 模型，LLM 参数保持不变 |
| **FluxMem（论文版）** — 记忆作为持续演化连接性 | 05-27 | 异构图拓扑建模记忆，三阶段持续优化 |
| **WorldMemArena** — 多模态 Agent 记忆评测 | 05-28 | 400 个多会话任务，阶段级评估（写入/维护/检索/使用），发现记忆质量提升≠性能改善 |

### A.3 社区讨论与工程实践

| 条目 | 来源 | 日期 | 要点 |
|------|------|------|------|
| **Token 消耗优化** — "工作流写入 Memory 的根本问题" | 宝玉 (@dotey) | 05-30 | 指出将工作流写入 Memory 方案的问题：Agent 每次需重新理解意图，token 消耗大。最佳实践：「Agent 技能+脚本」架构，LLM 仅做自然语言→SQL 转译 |
| **AI 主动记忆整合实践** — 从被动指令到数字分身 | Berry Xia | 05-28 | Memory OS 2.0 + Bloom AI 整合，强调 AI 主动记录而非被动指令 |
| **AgingBench** — Agent 记忆"衰老"问题 | Rohan Paul | 05-28 | Agent 部署后记忆系统因摘要/存储/更新而"衰老"，导致信息丢失、混淆、过时。提出 AgingBench 评估基准 |
| **睡眠巩固机制** — 周期性暂停以巩固记忆 | Rohan Paul | 05-28 | 效仿人类睡眠机制，加入周期性"睡眠阶段"：暂停、重读近期上下文、将有用信息写入长期存储 |
| **有效反馈计算（EFC）** — 更好的 Agent 通过记住有用反馈来扩展 | Rohan Paul | 06-01 | 提出 EFC 指标，仅统计正确、新颖、相关的反馈，过滤无效计算 |

### A.4 对你的项目的直接启示

1. **Hy-Memory 的 6 层框架值得深入研究** — 腾讯混元专门为 OpenClaw Agent 设计，与你的 AgentHub 多 CLI 场景高度相似。6 层 + System1/System2 双系统架构可能对方向 B 的 Phase C 设计有参考价值。

2. **Memory OS 的门控检索（Gated Retrieval）** — "门控"意味着不是每次用户消息都触发检索，而是有一个决策门控判断是否需要检索。你方向 B 的 `_maybe_inject_memories()` 中 `len(trigger.content.strip()) < 10` 就是最简单的门控。

3. **FluxMem 的「记忆即演化图」理念** — 记忆不是静态存储，而是持续演化。与你方向 B 的 Append-Only + 检索时解析策略方向一致，但更进一步：写入时建立连接、反馈驱动精炼。

4. **AgingBench 的警告** — Agent 记忆会"衰老"（信息过时、混淆）。你的 `ORDER BY updated_at DESC` 是天然的时间衰减，但需要警惕：如果旧记忆和新记忆冲突，Agent 能否正确分辨？

5. **宝玉的 Token 优化观点** — "Agent 技能+脚本"架构 vs "工作流写入 Memory"。你的 `[MEMORY:]` 标记路径避免了「每次重新理解意图」的问题——Agent 自主决定记什么，确定性高，不需要后端 LLM 重新理解。

---

*文档结束。此文为外部调研补充，不替代已有设计文档。实施决策以 `memory-system-direction-b-analysis.md` 和 `memory-feature-evaluation.md` 为准。*
