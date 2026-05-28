# 代码理解与知识图谱规范

> **本规范是 [ai-workflow 第二步 §2.9 工具链增强](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) 的细化**，把「用 MCP 代码理解工具替代 grep」展开成可执行标准。
> 它同时收拢了原先散落在 01/02/05/06 的调用图相关内容（调用关系标注、CALL_GRAPH、影响分析、代码地图、依赖黑洞检测），是这些主题的**唯一权威来源**。
>
> **启用门槛（最重要）**：仅 **中大型项目**（> 10 模块 或 > 5 万行）启用；轻量 / 小项目用 grep + 阅读即可，**不要为图谱付维护成本**。
> 具体工具的性能 / 召回率对比见 `docs/research/` 调研报告——数据随工具版本变化，本规范不固化数字。

---

## 一、核心概念

代码知识图谱 = **节点（实体）+ 边（关系）**，让 AI 用「图查询」（谁调用了我）替代「文本搜索」（字符串匹配）。

**节点类型**：`FUNCTION` / `CLASS` / `MODULE` / `API` / `CONFIG` / `SCHEMA`。

**关系类型（12 种）**：

| 静态可抽（基础层·规则引擎） | 需语义分析（增强层·LLM，按需启用） |
|---|---|
| `CALLS` 调用 · `IMPORTS` 导入 · `EXTENDS` 继承 | `DATAFLOW` 数据流 · `CONTROLFLOW` 控制流 |
| `IMPLEMENTS` 实现 · `CONTAINS` 包含 · `DEFINES` 定义 | `REFERENCES` 引用 · `ROUTES` 路由 · `CONFIGURES` 配置 · `DEPENDS_ON` 运行时依赖 |

---

## 二、图谱构建

| 规则 | 要点 | 强制 |
|------|------|------|
| AST 遍历抽取实体 | tree-sitter / ANTLR 解析；同名结合「文件路径 + 命名空间 + 类型」消歧 | 必须 |
| 跳过生成代码 | `__pycache__` / `node_modules` / `*.generated.*` 不纳入 | 必须 |
| 基础关系自动化 | 静态分析 100% 自动抽 CALLS/IMPORTS/EXTENDS/IMPLEMENTS/CONTAINS/DEFINES | 必须 |
| 增强关系按需 | LLM 成本高，仅对核心模块启用 DATAFLOW/REFERENCES 等 | 建议 |
| 增量优于全量 | 仅重分析变更文件及其直接依赖方；保存文件时由 file watcher / CI hook 触发 | 必须 |
| 全量重建兜底 | 每次收束节点或图结构不一致时执行一次全量重建 | 必须 |

---

## 三、查询与分析（图谱的真正用途）

### 3.1 变更影响分析（重构前必做 · 细化 [05 测试](05-testing_测试规范.md) 的影响范围定位）

```cypher
// 谁直接或间接调用了 calculate_discount？→ 受影响模块
MATCH (caller)-[:CALLS*1..3]->(f:FUNCTION {name:"calculate_discount"})
RETURN DISTINCT caller.module
```

流程：① 查上游调用者 → ② 列出受影响测试 → ③ 评估范围（模块/函数/风险）→ ④ 重构 → 跑受影响测试 → 全量回归。
CI 中按影响范围排序测试（直接 > 间接 > 无关），PR 增量跑、发布前兜底全量。

### 3.2 缺陷检测模式（配为 CI 门禁，命中即阻断）

| 模式 | 查询 | 等级 |
|------|------|------|
| 循环依赖 | `MATCH (a)-[:CALLS*2..]->(a) RETURN a` | 🔴 |
| 未使用函数 | `MATCH (f:FUNCTION) WHERE NOT (f)<-[:CALLS]-() RETURN f` | 🟡 |
| 上帝类 | `MATCH (c:CLASS)-[:DEFINES]->(f) WITH c,count(f) n WHERE n>20 RETURN c` | 🟡 |
| 跨层违规 | `MATCH (:CLASS{layer:"presentation"})-[:CALLS]->(:CLASS{layer:"infrastructure"}) RETURN *` | 🔴 |

> 跨层违规 / 循环依赖与 [01 架构红线](01-architecture_架构设计规范.md) 对应——图谱是它们在大型项目里的自动化检测手段。

### 3.3 可解释性

查询结果须给出**完整路径**（A→B→…→Z）并标注每条边的关系类型，不只给端点；影响范围量化为「受影响的模块数 / 函数数 / 测试数」。

---

## 四、代码内的标注（细化 [02 代码](02-coding_代码编写规范.md) 可理解性 · 中大型项目）

图谱工具自动生成基础版本，人工补业务语义。

```python
# @entrypoint — 订单创建入口，由 OrderController.create() 触发
def place_order(user_id: str, items: list[Item]) -> Order:
    """下单主流程。
    @callers: OrderController.create(), BatchOrderService.import_orders()
    @calls:   validate_stock(), calculate_price(), payment_service.charge()
    """
```

每个模块可放 `CALL_GRAPH.md`：列「对外暴露的接口（被谁调用）」+「外部依赖（调用谁）」。
打开陌生模块时，这些标注让人 30 秒内理解它在系统中的位置。

---

## 五、存储与工具选型（按规模）

| 规模 | 方案 | 查询 |
|------|------|------|
| < 5 万行 | SQLite + FTS5 | 全文搜索够用 |
| 5–50 万行 | KuzuDB（嵌入图 DB，零运维） | Cypher 图遍历 |
| > 50 万行 | Neo4j + APOC | 企业级、可视化 |

**推荐工具**（数据见调研报告，此处不固化）：CodeGraph（CI 自动调用图，增量监视）、CodeGraphContext（跨语言 / 死代码 / 圈复杂度）、Understand-Anything（交互式可视化、自动导览）、NetworkX + pydeps（Python 脚本分析）。

**设计权衡**：基础图谱用静态分析（精确、可解释、低成本），语义关系用 LLM 补充（仅核心模块）；默认函数 / 类级粒度，安全相关代码可下沉到 AST 级；优先覆盖主力语言（Python/TS/Java）。

---

## 六、代码地图 CODE_MAP（细化 [06 文档](06-documentation_文档规范.md) · 中大型必备）

`CODE_MAP.md` 放项目根或 `docs/`，让新人 5 分钟建全局心智模型，含三块：

1. **模块全景**（目录树 + 每个模块一句职责）
2. **调用关系**（Mermaid 全景图，从图谱生成 `MATCH (m:MODULE)-[:CALLS]->(n) RETURN m,n`）
3. **关键入口表**（HTTP 路由 / CLI 命令 / 事件处理器 / 定时任务，标位置）

随架构变更同步更新（PR 涉及模块增删改名时必更）。

---

## 七、维护与质量

| 检查项 | 频率 | 处理 |
|--------|------|------|
| 孤立节点（无入边无出边 / 依赖黑洞） | 每次构建 | 标「待确认」，连续 2 收束节点未确认 → 归档 |
| 孤儿模块（同职责散在多处） | 每次收束 | 社区检测发现，生成重组建议，人工确认 |
| 矛盾边 / 过时声明（代码已删图谱仍有） | PR / 构建 | 阻断或自动清理 |

| 版本控制 | 要点 |
|----------|------|
| `graph_schema.json`（节点/边定义）入 Git | 建议 |
| 图谱数据（`*.kuzu/`、`neo4j/data/`）入 `.gitignore`，CI 重建 | 必须 |

**覆盖目标**：业务代码实体 100%；CALLS/IMPORTS 关系 ≥ 95%；所有 public API 调用关系纳入统计。

---

## 八、检查清单

- [ ] 项目规模达到启用门槛（> 10 模块 / > 5 万行）才引入图谱
- [ ] 已选定存储方案（SQLite+FTS5 / KuzuDB / Neo4j）
- [ ] 配置了增量更新（非每次全量重建）
- [ ] CI 集成 ≥ 3 种缺陷检测模式（循环依赖 / 未用函数 / 跨层违规…）
- [ ] 重构前执行了上游影响分析
- [ ] 孤立节点已标记或清理
- [ ] `graph_schema.json` 入版本控制，图谱数据已 `.gitignore`
- [ ] 中大型项目有 `CODE_MAP.md`（全景图 + 关键入口表）
- [ ] 关键模块有 `@entrypoint` / `CALL_GRAPH.md` 标注

---

## 九、关联

| 方向 | 链接 |
|------|------|
| 细化自 | [ai-workflow §2.9 工具链增强](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) |
| 调研数据来源 | `docs/research/` 调研报告 |
| 跨层 / 循环依赖红线 | [01-架构设计规范](01-architecture_架构设计规范.md) |
| 代码标注 / 可理解性 | [02-代码编写规范](02-coding_代码编写规范.md) |
| 影响分析驱动的增量测试 | [05-测试规范](05-testing_测试规范.md) |
| 代码地图 / 知识互联 | [06-文档规范](06-documentation_文档规范.md) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-27 | v2.0 | 重构为 §2.9 的细化；设启用门槛；删全部报告引用与固化数字；收拢 01/02/05/06 的调用图内容成唯一权威 |
| 2026-05-27 | v1.0 | 初稿，8 章结构 |
