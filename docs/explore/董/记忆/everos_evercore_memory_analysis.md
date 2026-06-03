# EverOS (EverCore) 记忆系统深度分析

> EverOS 是一个专注于 AI Agent 长期记忆的统一系统，本文档分析其记忆架构和实现机制。

---

## 一、项目概览

### 1.1 基本信息

| 属性 | 值 |
|------|-----|
| **GitHub** | https://github.com/EverMind-AI/EverOS |
| **定位** | AI Agent 长期记忆操作系统 |
| **核心模块** | EverCore (记忆操作系统) |
| **语言** | Python 3.12+ |
| **评估分数** | LoCoMo 93.05% · LongMemEval 83.00% |

### 1.2 核心组件

```
EverOS
├── methods/
│   ├── EverCore/          # 核心记忆操作系统
│   └── HyperMem/          # 超图记忆架构
├── benchmarks/
│   ├── EverMemBench/      # 记忆质量评估
│   └── EvoAgentBench/     # Agent 自我进化评估
└── use-cases/
    ├── claude-code-plugin/ # Claude Code 记忆插件
    ├── openher/           # 人格引擎
    └── hive/              # 多 Agent 协作
```

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EverCore 架构                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        应用层 (Application Layer)                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │   │
│  │  │Claude    │  │  Chat    │  │  Game    │  │ Browser  │       │   │
│  │  │Code      │  │  Bot     │  │  Agent   │  │  Agent   │       │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        API 层 (API Layer)                         │   │
│  │                   FastAPI Server (Port 1995)                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      业务层 (Business Layer)                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │   │
│  │  │ SearchMem    │  │  GetMem     │  │  AddMem     │         │   │
│  │  │   Service   │  │   Service   │  │   Service   │         │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      记忆层 (Memory Layer)                        │   │
│  │  ┌────────────────────────────────────────────────────────┐    │   │
│  │  │                  MemoryManager                           │    │   │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐       │    │   │
│  │  │  │ MemCell   │  │ Episode    │  │ Foresight  │       │    │   │
│  │  │  │ Extractor │  │ Extractor  │  │ Extractor  │       │    │   │
│  │  │  └────────────┘  └────────────┘  └────────────┘       │    │   │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐       │    │   │
│  │  │  │  Profile   │  │  Atomic    │  │  Agent     │       │    │   │
│  │  │  │ Extractor │  │  Fact      │  │  Case      │       │    │   │
│  │  │  └────────────┘  └────────────┘  └────────────┘       │    │   │
│  │  └────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      基础设施层 (Infrastructure Layer)             │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐              │   │
│  │  │MongoDB │  │Elastic │  │ Milvus │  │  Redis │              │   │
│  │  │(存储)  │  │search  │  │(向量)  │  │(缓存)  │              │   │
│  │  └────────┘  └────────┘  └────────┘  └────────┘              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 组件 | 用途 | 端口 |
|------|------|------|
| **MongoDB** | 记忆文档存储 | 27017 |
| **Elasticsearch** | 全文搜索、关键词检索 | 19200 |
| **Milvus** | 向量相似度检索 | 19530 |
| **Redis** | 缓存、会话状态 | 6379 |
| **FastAPI** | REST API 服务 | 1995 |

---

## 三、记忆类型体系

### 3.1 记忆类型分类

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           记忆类型层次结构                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  RawData (原始对话)                                                     │
│       │                                                               │
│       ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         MemCell                                  │   │
│  │                    (对话边界检测结果)                            │   │
│  │  - 原始数据聚合                                                │   │
│  │  - 时间戳                                                      │   │
│  │  - 参与者                                                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                               │
│       ├──────────────────────┬──────────────────────┬──────────────┐    │
│       ▼                      ▼                      ▼               ▼    │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐    ┌─────────┐│
│  │ Episode  │         │ Foresight│         │ Atomic   │    │ Profile ││
│  │  Memory  │         │  预测    │         │  Fact    │    │ Memory ││
│  │  叙事记忆│         │          │         │ 原子事实 │    │ 用户画像││
│  └──────────┘         └──────────┘         └──────────┘    └─────────┘│
│       │                                                               │
│       ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       AgentCase                                 │   │
│  │                    (Agent 经验案例)                              │   │
│  │  - task_intent: 任务意图                                        │   │
│  │  - approach: 执行方法                                          │   │
│  │  - quality_score: 质量评分                                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                               │
│       ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       AgentSkill                                │   │
│  │                    (可复用技能，从案例聚类)                      │   │
│  │  - cluster_id: 聚类 ID                                         │   │
│  │  - maturity_score: 成熟度                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 各记忆类型详解

#### 3.2.1 MemCell (对话单元)

```python
@dataclass
class MemCell:
    """对话边界检测结果 - 原始对话的聚合单元"""
    
    # 必需字段
    user_id_list: List[str]              # 用户 ID 列表
    original_data: List[Dict]            # 原始消息列表
    timestamp: datetime                   # 时间戳
    
    # 可选字段
    event_id: Optional[str] = None        # 数据库生成的事件 ID
    group_id: Optional[str] = None        # 群组 ID
    participants: Optional[List[str]] = None  # 参与者
    sender_ids: Optional[List[str]] = None    # 发送者 ID
    type: Optional[RawDataType] = None   # 数据类型
    
    # 缓存的过滤数据
    _conversation_data_cache: Optional[List] = None
    
    @property
    def conversation_data(self):
        """返回过滤掉工具调用后的对话数据"""
        # 对于 AGENTCONVERSATION 类型，过滤掉中间步骤
        # tool_calls 和 tool 角色消息被排除
```

**关键特性**：
- 智能过滤中间工具调用步骤
- 保留用户意图和最终结果

#### 3.2.2 EpisodeMemory (叙事记忆)

```python
@dataclass
class EpisodeMemory(BaseMemory):
    """叙事记忆 - 事件的故事化描述"""
    
    id: Optional[str] = None
    subject: Optional[str] = None        # 主题
    summary: Optional[str] = None       # 摘要
    episode: Optional[str] = None        # 完整叙述
    parent_type: Optional[str] = None   # 父类型
    parent_id: Optional[str] = None    # 父 ID
```

**特点**：
- 完整的叙述性描述
- 包含主题和摘要
- 可用于 RAG 检索

#### 3.2.3 Foresight (预测记忆)

```python
@dataclass
class Foresight(BaseMemory):
    """预测记忆 - 从对话中提取的未来预测"""
    
    foresight: Optional[str] = None      # 预测内容
    evidence: Optional[str] = None       # 证据
    start_time: Optional[str] = None     # 开始时间
    end_time: Optional[str] = None      # 结束时间
    duration_days: Optional[int] = None # 持续天数
    parent_type: Optional[str] = None   # 父类型
    parent_id: Optional[str] = None     # 父 ID
```

**用途**：
- 提取用户/AI 的未来计划
- 关联时间维度的记忆

#### 3.2.4 AtomicFact (原子事实)

```python
@dataclass
class AtomicFact(BaseMemory):
    """原子事实 - 不可分割的事实单元"""
    
    time: Optional[str] = None               # 时间
    atomic_fact: Optional[Union[str, List]] = None  # 原子事实
    fact_embeddings: Optional[List[List]] = None      # 事实向量
    parent_type: Optional[str] = None
    parent_id: Optional[str] = None
```

**特点**：
- 最细粒度的记忆单元
- 支持多向量嵌入
- 可用于知识图谱构建

#### 3.2.5 ProfileMemory (用户画像)

```python
@dataclass
class ProfileMemory(BaseMemory):
    """用户画像 - 显式信息 + 隐式特征"""
    
    # 显式信息 (用户直接告诉的)
    explicit_info: List[Dict] = field(default_factory=list)
    # item: {"category": str, "description": str, "evidence": str, "sources": [str]}
    
    # 隐式特征 (从行为中推断的)
    implicit_traits: List[Dict] = field(default_factory=list)
    # item: {"trait": str, "description": str, "basis": str, "evidence": str, "sources": [str]}
    
    last_updated: Optional[datetime] = None        # 最后更新时间
    processed_episode_ids: List[str] = field(default_factory=list)  # 已处理的记忆 ID
```

**示例**：
```python
# 显式信息
explicit_info = [
    {"category": "职业", "description": "后端开发工程师", "evidence": "用户自我介绍", "sources": ["msg_001"]},
    {"category": "技能", "description": "熟悉 Java 和 Python", "evidence": "工作讨论", "sources": ["msg_003"]},
]

# 隐式特征
implicit_traits = [
    {"trait": "偏好简洁", "description": "喜欢简洁的代码风格", "basis": "代码审查评论", "evidence": "多次提到代码要简洁", "sources": ["msg_005"]},
]
```

#### 3.2.6 AgentCase (Agent 经验)

```python
@dataclass
class AgentCase(BaseMemory):
    """Agent 经验 - 从 Agent 对话中提取的经验"""
    
    task_intent: Optional[str] = None       # 任务意图 (检索关键字)
    approach: Optional[str] = None          # 执行方法 (步骤描述)
    quality_score: Optional[float] = None    # 质量评分 (0.0-1.0)
    key_insight: Optional[str] = None        # 关键洞察
    parent_type: Optional[str] = None
    parent_id: Optional[str] = None
```

**用途**：
- 记录 Agent 解决问题的完整过程
- 质量评分用于评估经验价值
- 可聚类形成 AgentSkill

#### 3.2.7 AgentSkill (Agent 技能)

```python
@dataclass
class AgentSkill(BaseMemory):
    """Agent 技能 - 从案例聚类中提取的可复用技能"""
    
    name: Optional[str] = None               # 技能名称
    description: Optional[str] = None       # 技能描述
    content: Optional[str] = None           # 完整内容
    confidence: float = 0.0                 # 置信度
    cluster_id: Optional[str] = None        # 聚类 ID
    maturity_score: float = 0.6             # 成熟度 (初始 0.6)
```

---

## 四、记忆提取流程

### 4.1 完整提取流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         记忆提取流程                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. 原始对话输入                                                       │
│     ┌─────────────────────────────────────────────────────────────┐   │
│     │ messages = [                                                 │   │
│     │   {"role": "user", "content": "帮我优化这个接口"},           │   │
│     │   {"role": "assistant", "content": "我来帮你分析..."},      │   │
│     │   {"role": "tool", "content": "代码分析结果..."},           │   │
│     │   {"role": "assistant", "content": "建议使用缓存..."}       │   │
│     │ ]                                                            │   │
│     └─────────────────────────────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│  2. MemCell 边界检测 (ConvMemCellExtractor)                          │
│     ┌─────────────────────────────────────────────────────────────┐   │
│     │ • 分析对话流                                                 │   │
│     │ • 检测主题边界                                               │   │
│     │ • 过滤中间工具调用                                           │   │
│     │ • 输出完整对话单元                                           │   │
│     └─────────────────────────────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│  3. 多类型记忆并行提取                                                │
│     ┌──────────────────┬──────────────────┬──────────────────┐     │
│     │ EpisodeExtractor │ ForesightExtractor│ ProfileExtractor │     │
│     │    ↓            │      ↓           │      ↓          │     │
│     │ 叙事记忆        │   预测记忆        │   用户画像      │     │
│     └──────────────────┴──────────────────┴──────────────────┘     │
│                              │                                         │
│                              ▼                                         │
│  4. 存储到多数据库                                                    │
│     ┌──────────────────┬──────────────────┬──────────────────┐     │
│     │   MongoDB       │  Elasticsearch   │     Milvus      │     │
│     │ (文档存储)       │  (全文搜索)      │   (向量检索)    │     │
│     └──────────────────┴──────────────────┴──────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 MemoryManager 核心逻辑

```python
class MemoryManager:
    """
    记忆管理器 - 协调所有记忆提取过程
    
    职责：
    1. MemCell 边界检测
    2. 多种记忆类型提取
    3. 管理所有提取器生命周期
    4. 提供统一的记忆提取接口
    """
    
    async def extract_memcell(self, history_raw_data_list, new_raw_data_list):
        """边界检测 - 判断是否形成完整的对话单元"""
        
    async def extract_memory(self, memcell, memory_type):
        """根据类型提取特定记忆"""
        
        match memory_type:
            case MemoryType.EPISODIC_MEMORY:
                return await self._extract_episode(memcell, user_id, group_id)
            case MemoryType.FORESIGHT:
                return await self._extract_foresight(memcell, ...)
            case MemoryType.ATOMIC_FACT:
                return await self._extract_atomic_fact(memcell, ...)
            case MemoryType.PROFILE:
                return await self._extract_profile(memcell, ...)
            case MemoryType.AGENT_CASE:
                return await self._extract_agent_case(memcell, ...)
```

---

## 五、检索机制

### 5.1 混合检索架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         混合检索流程                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  用户查询: "用户最近在做什么项目？"                                       │
│                              │                                          │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Query Processing                               │   │
│  │  • 向量化 (Embedding)                                            │   │
│  │  • 分词 (Tokenization)                                           │   │
│  │  • 意图识别                                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                    │                                                    │
│         ┌─────────┼─────────┐                                        │
│         ▼         ▼         ▼                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                              │
│  │  Vector  │ │  Full   │ │ Keyword  │                              │
│  │  Search  │ │  Text   │ │  Search  │                              │
│  │ (Milvus) │ │ Search  │ │   (BM25) │                              │
│  │   ↓       │ │ (ES)    │ │   ↓      │                              │
│  │ Top-K    │ │  ↓      │ │ Top-K   │                              │
│  └──────────┘ └──────────┘ └──────────┘                              │
│         │         │         │                                         │
│         └─────────┼─────────┘                                         │
│                   ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Score Fusion                                    │   │
│  │           RRF (Reciprocal Rank Fusion)                            │   │
│  │  Score = α × vector + β × full_text + γ × keyword               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Reranking (可选)                                │   │
│  │              Cross-Encoder 精排                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│                        Top Results                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 检索 API

```python
# 存储记忆
POST /api/v1/memories
{
    "user_id": "user_001",
    "session_id": "session_001",
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ]
}

# 搜索记忆
POST /api/v1/memories/search
{
    "query": "用户的技术偏好",
    "method": "hybrid",           # hybrid / vector / keyword
    "memory_types": ["profile"],  # 过滤记忆类型
    "top_k": 5,
    "filters": {"user_id": "user_001"}
}
```

---

## 六、与 CLI 的集成

### 6.1 Claude Code 插件

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Claude Code + EverCore 集成                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                      Claude Code CLI                           │     │
│  │  ┌─────────────────────────────────────────────────────────┐ │     │
│  │  │  hooks/                                                   │ │     │
│  │  │  • session-start: 加载历史记忆到上下文                   │ │     │
│  │  │  • session-end: 保存当前会话到记忆                      │ │     │
│  │  │  • prompt-submit: 注入相关记忆到 System Prompt          │ │     │
│  │  └─────────────────────────────────────────────────────────┘ │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼ HTTP/WebSocket                          │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                      EverCore API (Port 1995)                 │     │
│  │  • POST /memories - 存储记忆                                  │     │
│  │  • POST /memories/search - 检索记忆                          │     │
│  │  • GET /memories - 获取记忆                                  │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                     Milvus + MongoDB                           │     │
│  │  • 向量索引                                                    │     │
│  │  • 文档存储                                                    │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 集成流程

```python
# 1. Claude Code 启动时
@hook_impl
def session_start():
    # 1. 获取用户 ID
    user_id = get_current_user()
    
    # 2. 检索相关记忆
    memories = requests.post(
        f"{EVERCORE_API}/memories/search",
        json={"query": "项目背景", "filters": {"user_id": user_id}}
    )
    
    # 3. 注入到 System Prompt
    inject_to_system_prompt(memories)

# 2. Claude Code 结束时
@hook_impl
def session_end():
    # 1. 收集会话消息
    messages = collect_session_messages()
    
    # 2. 存储到 EverCore
    requests.post(
        f"{EVERCORE_API}/memories",
        json={"user_id": user_id, "messages": messages}
    )
```

---

## 七、数据结构总结

### 7.1 核心数据结构

| 类型 | 用途 | 粒度 | 存储 |
|------|------|------|------|
| **MemCell** | 对话单元边界 | 中 | MongoDB |
| **EpisodeMemory** | 叙事记忆 | 粗 | MongoDB + ES |
| **Foresight** | 预测记忆 | 中 | MongoDB |
| **AtomicFact** | 原子事实 | 细 | MongoDB + Milvus |
| **ProfileMemory** | 用户画像 | 中 | MongoDB |
| **AgentCase** | Agent 经验 | 粗 | MongoDB + Milvus |
| **AgentSkill** | Agent 技能 | 粗 | MongoDB |

### 7.2 关键字段

```python
# BaseMemory 通用字段
@dataclass
class BaseMemory:
    memory_type: Union[MemoryType, str]   # 记忆类型
    user_id: str                          # 用户 ID
    timestamp: datetime                   # 时间戳
    group_id: Optional[str] = None        # 群组 ID
    participants: Optional[List[str]] = None  # 参与者
    keywords: Optional[List[str]] = None   # 关键词
    linked_entities: Optional[List[str]] = None  # 关联实体
    vector_model: Optional[str] = None     # 向量模型
    vector: Optional[List[float]] = None  # 向量
    score: Optional[float] = None          # 检索得分
```

---

## 八、优缺点分析

### 8.1 优点

| 优点 | 说明 |
|------|------|
| **多层次记忆** | 从原子事实到叙事记忆，粒度完整 |
| **多类型提取** | Episode/Foresight/Profile/AgentCase 并行提取 |
| **混合检索** | 向量 + 全文 + 关键词，多路召回 |
| **自我进化** | AgentCase → AgentSkill 聚类进化 |
| **评估体系** | EverMemBench + EvoAgentBench 完整评测 |
| **模块化设计** | 易于扩展新记忆类型 |

### 8.2 缺点

| 缺点 | 说明 |
|------|------|
| **部署复杂** | 依赖 4 个数据库服务 |
| **资源消耗** | 需要较高配置服务器 |
| **API 延迟** | HTTP 调用比本地记忆慢 |
| **边界检测复杂** | MemCell 提取依赖 LLM |

---

## 九、与 cc-haha 对比

| 维度 | EverCore | cc-haha |
|------|----------|---------|
| **记忆类型** | 7 种 (完整体系) | 3 种 (Auto/Agent/Team) |
| **检索方式** | 混合检索 (Vector+ES+BM25) | AI 语义选择 |
| **存储后端** | MongoDB + ES + Milvus + Redis | 文件系统 |
| **提取方式** | 全自动 (LLM 提取) | 半自动 (用户标记 + AI 选择) |
| **Agent 经验** | ✅ AgentCase → AgentSkill | ❌ 不支持 |
| **部署复杂度** | 高 (4 个服务) | 低 (单进程) |
| **适用场景** | 企业级、长期记忆 | 个人开发者 |

---

## 十、参考资源

| 资源 | 链接 |
|------|------|
| GitHub | https://github.com/EverMind-AI/EverOS |
| 文档 | https://docs.evermind.ai |
| 论文 | https://arxiv.org/abs/2601.02163 |
| Claude Code 插件 | use-cases/claude-code-plugin/ |
| Hive (多 Agent) | https://github.com/tt-a1i/hive |

---

*文档更新时间：2025-01-15*
