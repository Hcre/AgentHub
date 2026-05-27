// ============================================================
// 代码知识图谱 — 常用查询模板
// 对应规范 §3.1-§3.3
// 查询语言: Cypher（兼容 KuzuDB / Neo4j）
// ============================================================

// ── 3.2 依赖分析 ──────────────────────────────────

// 上游分析：谁调用了我？（变更影响评估）
// 找到所有直接或间接调用 target_func 的模块
MATCH (caller:FUNCTION)-[:CALLS*1..3]->(target:FUNCTION {name: $func_name})
RETURN DISTINCT caller.module AS affected_module, caller.name AS caller_name
ORDER BY affected_module;


// 下游分析：我调用了谁？（理解函数实现依赖）
MATCH (source:FUNCTION {name: $func_name})-[:CALLS]->(callee:FUNCTION)
RETURN callee.name, callee.module, callee.signature;


// 模块间依赖全景
MATCH (m1:MODULE)-[:IMPORTS]->(m2:MODULE)
RETURN m1.name AS source_module, m2.name AS target_module
ORDER BY source_module;


// ── 3.3 缺陷检测 ──────────────────────────────────

// 1) 循环依赖检测
MATCH path = (a:MODULE)-[:IMPORTS*2..5]->(a)
RETURN a.name AS module, length(path) AS cycle_length, nodes(path) AS cycle_path
LIMIT 20;


// 2) 未使用函数（未被任何调用者 CALLS 且非入口点）
MATCH (f:FUNCTION)
WHERE NOT (f)<-[:CALLS]-()
  AND NOT f.is_entrypoint
RETURN f.name, f.module, f.line
ORDER BY f.module;


// 3) 上帝类（方法数超过 20 的类）
MATCH (c:CLASS)-[:DEFINES]->(f:FUNCTION)
WITH c, count(f) AS method_count
WHERE method_count > 20
RETURN c.name, c.module, method_count
ORDER BY method_count DESC;


// 4) 跨层违规（表现层直接调用基础设施层）
MATCH (controller:FUNCTION {layer: "presentation"})-[:CALLS]->(db:FUNCTION {layer: "infrastructure"})
RETURN controller.name, controller.module, db.name, db.module;


// 5) 未处理异常的调用
MATCH (f:FUNCTION)-[:CALLS]->(g:FUNCTION)
WHERE g.throws IS NOT NULL AND f.handles_exception = false
RETURN f.name AS caller, g.name AS callee, g.throws AS exception_type;


// ── 6.1 代码语义搜索 ─────────────────────────────

// 按函数名模糊搜索
MATCH (f:FUNCTION)
WHERE f.name CONTAINS $keyword
RETURN f.name, f.module, f.signature, f.docstring
LIMIT 20;


// 按文档描述搜索（全文索引需要 FTS 插件）
// CALL db.index.fulltext.queryNodes("functionDocs", $keyword)
// YIELD node, score
// RETURN node.name, node.module, score;


// ── 6.2 重构影响范围 ─────────────────────────────

// 找到所有受影响的测试函数
MATCH (target:FUNCTION {name: $changed_func})<-[:CALLS*1..5]-(test:FUNCTION)
WHERE test.name STARTS WITH "test_"
RETURN DISTINCT test.name AS test_name, test.module AS test_file
ORDER BY test_file;


// ── 7.1 图谱 Lint（收束节点触发） ───────────────────

// 孤立节点检测（无入边 + 无出边）
MATCH (n)
WHERE NOT (n)<-[:CALLS|IMPORTS|EXTENDS|IMPLEMENTS|CONTAINS|DEFINES|ROUTES|CONFIGURES|DATAFLOW|CONTROLFLOW|REFERENCES|DEPENDS_ON]-()
  AND NOT (n)-[:CALLS|IMPORTS|EXTENDS|IMPLEMENTS|CONTAINS|DEFINES|ROUTES|CONFIGURES|DATAFLOW|CONTROLFLOW|REFERENCES|DEPENDS_ON]->()
  AND NOT n:MODULE  // 排除模块自身
RETURN n.type, n.name, n.module;
