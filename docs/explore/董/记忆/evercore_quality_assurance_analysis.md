# EverCore 记忆系统质量保证机制深度分析

## 一、质量保证体系概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     EverCore 记忆质量保证体系                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    评估基准 (Benchmarks)                           │   │
│  │  ┌─────────────────┐    ┌─────────────────┐                   │   │
│  │  │ EverMemBench    │    │  EvoAgentBench   │                   │   │
│  │  │ (记忆质量评估)   │    │  (Agent进化评估) │                   │   │
│  │  │ LoCoMo: 93.05% │    │  5个领域测试    │                   │   │
│  │  │ LongMem: 83.00% │    │  Train/Test分割  │                   │   │
│  │  └─────────────────┘    └─────────────────┘                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      提取质量控制                                   │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │   │
│  │  │  置信度评分    │  │  质量评分      │  │  成熟度评分    │   │   │
│  │  │ confidence    │  │ quality_score │  │ maturity_score │   │   │
│  │  │   (0.0-1.0)   │  │   (0.0-1.0)   │  │   (0.0-1.0)   │   │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      检索质量控制                                   │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │   │
│  │  │  多路召回      │  │  RRF融合      │  │  阈值过滤     │   │   │
│  │  │ Vector+ES+BM25│  │  Reciprocal   │  │ score >= 阈值  │   │   │
│  │  │               │  │  Rank Fusion  │  │               │   │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、评估基准 (Benchmarks)

### 2.1 EverMemBench - 记忆质量评估

EverMemBench 是一个综合性的多人群聊评估框架，支持对记忆系统进行完整评估。

#### 评估流程

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
│   Add   │ -> │  Search  │ -> │  Answer  │ -> │ Evaluate  │
└─────────┘    └──────────┘    └──────────┘    └───────────┘
     │              │               │               │
     ▼              ▼               ▼               ▼
  Ingest       Retrieve LLM      Generate       Assess
 memories     memories        answers       accuracy
```

| 阶段 | 描述 | 输出 |
|------|------|------|
| **Add** | 将对话数据摄入记忆系统 | - |
| **Search** | 检索相关记忆用于问答 | `search_results_{user_id}.json` |
| **Answer** | 使用 LLM + 检索上下文生成答案 | `answer_results_{user_id}.json` |
| **Evaluate** | 评估答案质量 (MC: 直接比较, OE: LLM评判) | `evaluation_results_{user_id}.json` |

#### 支持的记忆系统

| 系统 | 时间戳支持 | 消息格式 | 环境变量 |
|------|-----------|----------|----------|
| **Memos** | Native `chat_time` | `[Group: X][Speaker: Y]content` | `MEMOS_API_KEY`, `MEMOS_BASE_URL` |
| **Mem0** | Native `timestamp` | `run_id="${user_id}_${groupId}"` | `MEM0_API_KEY` |
| **Memobase** | Native `created_at` | `[Group: X][Speaker: Y]content` | `MEMOBASE_BASE_URL` |
| **EverCore** | Native `create_time` | `sender=<Speaker>`, `group_id` | `EVERMEMOS_BASE_URL` |
| **Zep** | Native `created_at` | `[Group: X][Speaker: Y]content` | `ZEP_API_KEY` |

#### 评估指标

| 指标 | 值 | 说明 |
|------|-----|------|
| **LoCoMo** | 93.05% | 长对话上下文理解能力 |
| **LongMemEval** | 83.00% | 长期记忆检索准确性 |

### 2.2 EvoAgentBench - Agent 进化评估

EvoAgentBench 是统一评估 AI Agent 自我进化能力的框架。

#### 评估领域

| 领域 | 基础基准 | 描述 | Train | Test |
|------|---------|------|-------|------|
| Information Retrieval | BrowseCompPlus | 搜索语料库回答多约束问题 | 154 | 65 |
| Reasoning | OmniMath | 竞赛级数学问题 | 478 | 100 |
| Software Engineering | SWE-Bench | 修复开源项目 bug | 101 | 26 |
| Code Implementation | LiveCodeBench | 竞赛编程 | 97 | 39 |
| Knowledge Work | GDPVal | 真实职业任务 | 87 | 58 |

#### 自我进化方法对比

| 方法 | 方案 | 说明 |
|------|------|------|
| **EverCore** | 基于记忆的技能提取 | 从轨迹中提取可复用技能 |
| **EvoSkill** | 两步 proposer-generator | 自改进循环 |
| **Memento** | 基于案例的检索 | 相似性搜索 |
| **OpenSpace** | 技能积累 | analyze-evolve 流程 |
| **Reasoning Bank** | 推理模式库 | 可复用推理模式 |

## 三、提取质量控制

### 3.1 三层评分体系

| 评分类型 | 字段 | 范围 | 用途 | 阈值 |
|---------|------|------|------|------|
| **confidence** | 置信度 | 0.0-1.0 | 技能提取的可靠性 | retire < 0.1 |
| **quality_score** | 质量分 | 0.0-1.0 | 任务完成质量 | success >= 0.5 |
| **maturity_score** | 成熟度 | 0.0-1.0 | 技能是否可检索 | retrievable >= 0.6 |

### 3.2 AgentCase 质量评分

```python
# agent_case_extractor.py
quality_score = self._clamp_quality_score(exp_dict.get("quality_score", 0.5))
```

#### 评分标准（来自 prompts/en/agent_prompts.py）

```
quality_score: 0.0-1.0 measuring task completion and deliverable quality
— NOT effort, exploration depth, or number of steps attempted.

评分规则:
1. 基于最终交付物状态，不是过程
   - 探索了10种方法但无产出 = 低分
   - 直接给出解决方案 = 高分

2. 外部阻塞（资源不可用、OOM）按实际产出评分
   - 不因无法控制的原因降低分数

3. 失败案例 (quality_score < 0.5)
   - 代表完全或大部分失败
   - 记录尝试的步骤及失败原因
```

### 3.3 AgentSkill 成熟度评估

```python
# agent_skill_extractor.py
# 成熟度从 4 个维度评估（每个 1-5 分）:

completeness:  完整性 - 步骤是否完整覆盖流程
executability:  可执行性 - 步骤是否可直接执行
evidence:       证据充分性 - 示例和验证是否充分
clarity:        清晰度 - 表达是否清晰易懂

# 最终分数计算
raw_total = completeness + executability + evidence + clarity  # 4-20
maturity_score = raw_total / 20.0  # 归一化到 0-1

# 成熟度阈值
maturity_threshold = 0.6  # >= 0.6 才可被检索
```

### 3.4 置信度更新规则

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        置信度更新规则                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  新建技能 (add):              confidence = 0.5                        │
│                                                                         │
│  假设→验证提升 (promotion):   confidence = 0.6                         │
│  (## Potential Steps → ## Steps)                                        │
│                                                                         │
│  新决策分支 (new logic):      confidence = existing + 0.1             │
│                               (上限 cap 0.95)                           │
│                                                                         │
│  确认性更新 (confirming):     confidence = existing + 0.05           │
│  (无新决策逻辑，仅确认)         (上限 cap 0.95)                          │
│                                                                         │
│  矛盾案例 (contradicting):    confidence = existing - 0.2             │
│  (与现有技能推荐方法冲突)       矛盾案例加入 Pitfalls                     │
│                                                                         │
│  低于阈值 (retire):           confidence < 0.1 → 技能退役              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.5 成熟度重评估触发条件

```python
# _rescore_maturity() - 判断何时需要重新评估成熟度

# 1. 变化 < 20%: 保持当前分数
if change_ratio < 0.2:
    pass  # keep current score

# 2. 变化 >= 40% 或假设提升: 始终通过 LLM 重新评分
if change_ratio >= 0.4 or promotion:
    await self._evaluate_maturity(...)
    return

# 3. 其他情况:
#    - 已成熟 (>= threshold) 且置信度未下降 → 跳过
#    - 未成熟 (< threshold) 且案例质量 < 0.3 → 跳过
#    - 否则 → 通过 LLM 重新评分
```

## 四、检索质量控制

### 4.1 混合检索架构

```python
# 检索方法配置
retrieve_method: "hybrid"  # hybrid / semantic / keyword

# 多路召回
┌─────────────────────────────────────────────────────────────┐
│                        查询输入                              │
└─────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    ┌───────────┐    ┌───────────┐    ┌───────────┐
    │ Vector    │    │Elastic    │    │   BM25    │
    │ Search    │    │Search     │    │ Keyword   │
    │(Milvus)   │    │(ES)       │    │ Retrieval │
    └───────────┘    └───────────┘    └───────────┘
          │                 │                 │
          ▼                 ▼                 ▼
    语义相似度        全文搜索          关键词匹配
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
                    ┌───────────────┐
                    │  RRF 融合    │
                    │ Reciprocal   │
                    │ Rank Fusion  │
                    └───────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  阈值过滤    │
                    │  排序输出    │
                    └───────────────┘
```

### 4.2 RRF 融合算法

```python
# Reciprocal Rank Fusion
# 多路检索结果按排名融合

def reciprocal_rank_fusion(results_by_modality):
    fused_scores = {}
    k = 60  # RRF 常数

    for modality, results in results_by_modality.items():
        for rank, item in enumerate(results):
            score = 1 / (k + rank + 1)
            fused_scores[item.id] = fused_scores.get(item.id, 0) + score

    return sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
```

### 4.3 阈值过滤

```python
# AgentSkill 检索阈值配置
search:
  top_k: 10
  maturity_threshold: >= 0.6    # 成熟度阈值
  confidence_threshold: >= 0.0  # 置信度阈值

# AgentCase 检索阈值配置
score_threshold: >= 0.0  # COSINE 相似度阈值

# ProfileMemory 检索配置
min_confidence: 0.6
```

### 4.4 智能 Boost 加权

```python
# _calculate_text_score() - 根据关键词重要性动态调整 boost

query_with_scores = [
    (word, self._calculate_text_score(word)) for word in query
]

sorted_query_with_scores = sorted(
    query_with_scores, key=lambda x: x[1], reverse=True
)

for word, word_score in sorted_query_with_scores:
    Q("match", search_content={
        "query": word,
        "boost": word_score  # 高频词 boost 更高
    })
```

## 五、自我进化与纠错机制

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        自我进化与纠错流程                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. 经验提取                                                           │
│     ┌─────────────────────────────────────────────────────────────┐      │
│     │ AgentCase {                                                 │      │
│     │   task_intent: "用户想要优化接口性能",                      │      │
│     │   approach: "使用 Redis 缓存 + 异步处理",                   │      │
│     │   quality_score: 0.85                                      │      │
│     │ }                                                           │      │
│     └─────────────────────────────────────────────────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│  2. 聚类                                                               │
│     相似任务聚类 → cluster_id                                           │
│                              │                                          │
│                              ▼                                          │
│  3. 技能提取                                                           │
│     ┌──────────────────────┬──────────────────────┐                     │
│     │ quality_score >= 0.5 │ quality_score < 0.5 │                     │
│     │ ↓                    │ ↓                    │                     │
│     │ AgentSkill (验证成功) │ AgentSkill (假设)    │                     │
│     │ ## Steps            │ ## Potential Steps   │                     │
│     │ confidence = 0.5   │ confidence = 0.5     │                     │
│     └──────────────────────┴──────────────────────┘                     │
│                              │                                          │
│                              ▼                                          │
│  4. 成熟度评估                                                         │
│     4 维度 × LLM 评判 → maturity_score                                 │
│     成熟度 >= 0.6 → 可检索                                             │
│                              │                                          │
│                              ▼                                          │
│  5. 后续验证                                                           │
│     ┌──────────────────────────────────────────────────────────────┐     │
│     │ 新案例验证技能     │ 置信度调整 (existing + 0.05~0.1)       │     │
│     │ 新决策分支出现     │ 置信度提升 (existing + 0.1)            │     │
│     │ 矛盾案例出现       │ 置信度下降 (existing - 0.2)            │     │
│     │                    │ 矛盾加入 Pitfalls                       │     │
│     │ 低于阈值 (< 0.1)   │ 技能退役 (Retire)                       │     │
│     └──────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 六、关键代码实现

### 6.1 质量评分计算

```python
# agent_case_extractor.py
def _clamp_quality_score(value: Any) -> Optional[float]:
    """Clamp quality_score to [0.0, 1.0], return None if invalid."""
    try:
        score = float(value)
        return max(0.0, min(1.0, score))
    except (TypeError, ValueError):
        return None

async def _extract_single_case(self, ...) -> Optional[dict]:
    # 调用 LLM 提取经验
    response = await self._call_llm(...)
    exp_dict = self._parse_json_response(response)

    return {
        "task_intent": exp_dict.get("task_intent"),
        "approach": exp_dict.get("approach"),
        "quality_score": self._clamp_quality_score(
            exp_dict.get("quality_score", 0.5)
        ),
    }
```

### 6.2 成熟度评估

```python
# agent_skill_extractor.py
async def _evaluate_maturity(
    self,
    name: str,
    description: str,
    content: str,
    confidence: float
) -> Optional[float]:
    """使用 LLM 评估技能成熟度 (4 维度 × 5 分制)"""

    response = await self._call_llm(
        AGENT_SKILL_MATURITY_SCORE_PROMPT,
        ...
    )

    # 解析评分
    scores = self._parse_maturity_scores(response)

    raw_total = (
        scores.completeness +
        scores.executability +
        scores.evidence +
        scores.clarity
    )

    # 归一化到 0-1
    score = max(0.0, min(1.0, raw_total / 20.0))

    return score if score >= self.maturity_threshold else None
```

### 6.3 置信度动态调整

```python
# agent_skill_extractor.py
def _calculate_confidence_update(
    self,
    existing_confidence: float,
    action: str,
    source_quality: float
) -> Dict[str, Any]:
    """根据操作类型计算新的置信度"""

    updates = {}

    if action == "add":
        updates["confidence"] = 0.5

    elif action == "update":
        data = action_data.get("data", {})
        new_confidence = data.get("confidence")

        if new_confidence is not None:
            clamped = max(0.0, min(1.0, float(new_confidence)))
            updates["confidence"] = clamped

    # 低于退役阈值
    final_confidence = updates.get("confidence")
    if final_confidence is not None and final_confidence < self.retire_confidence:
        # 标记为退役
        updates["retired"] = True

    return updates
```

## 七、与其他系统对比

| 维度 | EverCore | Mem0 | cc-haha | AgentMemory |
|------|----------|------|---------|-------------|
| **质量评估** | ✅ 多层评分 | ✅ 基础评分 | ❌ 无 | ❌ 无 |
| **成熟度机制** | ✅ maturity_score | ❌ 无 | ❌ 无 | ❌ 无 |
| **自我纠错** | ✅ 置信度动态调整 | ❌ 无 | ❌ 无 | ❌ 无 |
| **评估基准** | ✅ EverMemBench | ❌ 无 | ❌ 无 | ❌ 无 |
| **阈值过滤** | ✅ 多阈值 | ❌ 无 | ❌ 无 | ❌ 无 |
| **技能进化** | ✅ AgentSkill | ❌ 无 | ❌ 无 | ❌ 无 |
| **部署复杂度** | 高 (4服务) | 中 | 低 | 低 |
| **跨设备支持** | ✅ 云端存储 | ✅ 云端存储 | ❌ 本地文件 | ❌ 本地文件 |

## 八、总结

### 8.1 核心质量保证机制

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         质量保证核心公式                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  提取质量 = LLM生成 + 多层评分                                          │
│             ├─ confidence (置信度)                                       │
│             ├─ quality_score (质量分)                                    │
│             └─ maturity_score (成熟度)                                    │
│                                                                         │
│  检索质量 = 混合召回 + RRF融合 + 阈值过滤                               │
│             ├─ Vector + ES + BM25                                        │
│             ├─ 排名融合                                                  │
│             └─ 分数阈值                                                  │
│                                                                         │
│  进化质量 = 置信度调整 + 技能淘汰                                       │
│             ├─ 成功案例 → 置信度+                                        │
│             ├─ 矛盾案例 → 置信度-                                        │
│             └─ 低于阈值 → 退役                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 设计亮点

1. **量化可追踪**：所有质量指标都有明确的数值范围和阈值
2. **自动化进化**：基于置信度动态调整，无需人工干预
3. **评估闭环**：EverMemBench 提供持续的质量反馈
4. **多层防护**：提取→存储→检索→应用，每个环节都有质量控制

### 8.3 适用场景

| 场景 | 推荐度 | 说明 |
|------|--------|------|
| 企业级应用 | ⭐⭐⭐⭐⭐ | 需要可靠的质量保证 |
| 多 Agent 协作 | ⭐⭐⭐⭐⭐ | Agent 经验可复用 |
| 长期记忆系统 | ⭐⭐⭐⭐ | 自我纠错机制保证准确性 |
| 个人工具 | ⭐⭐ | 部署复杂度过高 |
| 快速原型 | ⭐⭐ | 需要更多配置工作 |

### 8.4 借鉴建议

对于需要构建记忆系统的项目，可以从 EverCore 借鉴：

1. **评分体系**：建立 confidence/quality/maturity 三层评分
2. **阈值机制**：设置可检索的最低成熟度阈值
3. **自我纠错**：通过置信度动态调整实现自动进化
4. **评估基准**：构建测试集验证记忆质量

## 九、参考资料

- [EverMemBench 论文](https://arxiv.org/pdf/2602.01313)
- [EverMemBench 数据集](https://huggingface.co/datasets/EverMind-AI/EverMemBench-Dynamic)
- [EvoAgentBench](https://evermind-ai.github.io/EvoAgentBench/)
