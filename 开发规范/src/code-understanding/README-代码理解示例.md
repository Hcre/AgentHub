# 代码理解与图谱示例

> **👤 人类参考** | 对应规范：`conventions/08-code-understanding_代码理解与图谱规范.md`
> 技术栈：Python 3.10+ + tree-sitter | 运行：`python call_graph_example.py .`

## 目录结构

```
code-understanding/
├── README-代码理解示例.md     # 本文件
├── call_graph_example.py     # AST 遍历构建调用图（实体抽取 + 关系抽取）
├── graph_schema.json         # 图数据库 schema 定义（KuzuDB/Neo4j 初始化用）
├── cypher_queries.cypher     # 常用图查询模板库（影响分析/缺陷检测/代码搜索）
└── ci_integration.py         # CI 集成检查脚本（循环依赖/未使用函数/跨层违规）
```

## 文件→规范章节映射

| 文件 | 对应规范章节 | 演示内容 |
|------|------------|---------|
| `call_graph_example.py` | §2.1 实体抽取 + §2.2 关系抽取 | `CodeGraph` 数据结构、`CallGraphVisitor` AST 遍历器、孤儿节点检测、Top-K 被调用函数统计 |
| `graph_schema.json` | §1.2 节点类型 + §1.3 边类型 + §4.1 存储方案 | 6 种实体 + 12 种关系 + KuzuDB/Neo4j 建表 DDL |
| `cypher_queries.cypher` | §3.1 查询语言 + §3.2 依赖分析 + §3.3 缺陷检测 + §6.1 语义搜索 | 上游/下游分析、5 种缺陷检测模式、模糊搜索、重构影响范围 |
| `ci_integration.py` | §3.3 缺陷检测 + §6.2 CI 门禁 + §7.1 图谱 Lint | `CyclicDependencyCheck`、`UnusedFunctionCheck`、`CrossLayerCheck`、JSON 报告输出 |

## 端到端使用流程

```
1. 构建图谱
   python call_graph_example.py <项目目录>
   → 输出：实体数 + 关系数 + 孤儿节点 + Top-5 被调用函数

2. 初始化图数据库（以 KuzuDB 为例）
   pip install kuzu
   # 按 graph_schema.json 的 node_types/edge_types 建表
   # 将 call_graph_example.py 的输出导入 KuzuDB

3. 运行图查询
   # 复制 cypher_queries.cypher 中的查询到 KuzuDB Explorer
   # 或通过 Python driver 直接执行

4. CI 集成
   python ci_integration.py --repo . --mode pr
   → 输出：JSON 报告（通过/失败 + 违规详情）
   → 退出码：0=全部通过, 1=存在违规
```

## 快速验证

```bash
# 安装依赖
pip install tree-sitter

# 1) 构建当前目录的调用图
python call_graph_example.py .

# 2) 运行 CI 检查（模拟数据，演示流程）
python ci_integration.py --mode pr
# 预期输出：3 项检查（循环依赖 ❌ + 未使用函数 ❌ + 跨层违规 ✅ → 2 违规）

# 3) 查看 Cypher 查询模板
cat cypher_queries.cypher
```

## 工具链配置参考

| 工具 | 安装命令 | 最小配置 | 适用场景 |
|------|---------|---------|---------|
| CodeGraph | `npm i -g @codegraph/cli` | `codegraph init` | CI 自动生成调用图 |
| KuzuDB (Python) | `pip install kuzu` | 导入 `graph_schema.json` | 嵌入图数据库，Cypher 查询 |
| pydeps | `pip install pydeps` | `pydeps src/ --show-deps` | Python 项目依赖可视化 |
| Neo4j | Docker 镜像 | 导入 `graph_schema.json` | 企业级图数据库 |
