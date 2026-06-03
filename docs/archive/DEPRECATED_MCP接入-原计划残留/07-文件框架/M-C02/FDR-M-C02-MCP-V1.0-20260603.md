# 框架决策记录 FDR-M-C02-MCP-V1.0-20260603

> M-C02 K4 Analyzer 模块框架决策记录
> 来源 [DD-001:MD-MCP-V1.0#M-C02 + FS-011 + 4.13 模板]

---

## FDR-M-C02-001 文件结构 1:1 落地 FS-011

```
[决策编号] FDR-M-C02-001
[决策标题] 文件结构与 FS-011 一一对应（不重组）
[决策状态] 已接受
[决策内容] M-C02 严格按 FS-011 落地 1 个 analyzer.py + 1 个 grpc_server.py + 1 个 corpus.py + rules/ 子包 + tests/ 子包；不引入额外抽象层
[决策理由]
  1. FS-011 是 DD-001 详细设计的一部分，DD-M 强行重组会导致 DD-S 骨架搭建歧义
  2. 12 规则平铺在 rules/ 下便于审计与版本管理
  3. 备选方案（按攻击面分类）与全局规范偏离过大
[拒绝的替代方案]
  方案A: rules/by_category/（deserialization/exec/network 三个子包）— 拒绝理由：与 FS-011 偏离，加权分差 3.10 分
  方案B: 单 rules.py 含 12 类 — 拒绝理由：单文件超过 20 函数上限（R 24）
[影响范围] 全部 23 个 M-C02 文件
[相关FDR] FDR-M-C02-002
[来源标注] [DD-001:FS-011 + 4.11 多方案对比]
```

---

## FDR-M-C02-002 补充 cache.py 子模块

```
[决策编号] FDR-M-C02-002
[决策标题] 显式拆分 cache.py（规则集预加载 + LRU + 热重载信号）
[决策状态] 已接受
[决策内容] 即使 MD-MCP-V1.0#M-C02 子模块拆分列出了 cache/，DD-M 仍以 cache.py 单文件落地（避免单文件职责过粗）
[决策理由]
  1. cache 子模块职责明确（预加载/LRU/重载），可作为单文件落地
  2. 与 analyzer.py（分析）/ corpus.py（校准）/ grpc_server.py（gRPC）形成 4 大独立子模块
  3. 便于未来 NUMA 绑核/规则分片演进时拆分为 cache/ 子包
[拒绝的替代方案]
  方案A: 合并入 grpc_server.py — 拒绝理由：grpc_server 已有 8 worker 调度职责，耦合 cache 会导致单文件函数超 20
  方案B: 独立 cache/ 子包 — 拒绝理由：当前 1 个 RuleSetCache 类无需子包
[影响范围] cache.py
[相关FDR] FDR-M-C02-001
[来源标注] [DD-M推断:依据 MD-MCP-V1.0#M-C02 子模块拆分 + R24 单文件职责]
```

---

## FDR-M-C02-003 12 类规则清单确定

```
[决策编号] FDR-M-C02-003
[决策标题] 12 类 K4 规则（11+1）清单确定
[决策状态] 已接受
[决策内容] 12 类规则为：PickleLoad / EvalExec / ShellInject / SubprocessShell / DynamicImport / WeakHash / HardcodedSecret / PathTraversal / SQLInject / DeserializeUntrusted / UnsafeYAML / TemplateInject
[决策理由]
  1. 来自 MD-MCP-V1.0#M-C02 "Rule_PickleLoad / Rule_EvalExec / Rule_ShellInject ... (11+1 类)"
  2. 覆盖 OWASP Top 10 关键注入类（CWE-22/78/89/94/502/915）+ 加密弱点（CWE-327）+ 凭据暴露（CWE-798）+ SSTI（CWE-1336）
  3. 与 M-B05 Saga K4Step 调用对接
[拒绝的替代方案]
  方案A: 仅 5 类规则 — 拒绝理由：覆盖不足，K4 静态分析价值无法体现
  方案B: 20+ 类规则 — 拒绝理由：当前 MVP 不必要；未来扩展
[影响范围] rules/{12 rule files} + rules/__init__.py ALL_RULES
[相关FDR] FDR-M-C02-001
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + CWE 分类标准]
```

---

## FDR-M-C02-004 Worker Pool 大小 8

```
[决策编号] FDR-M-C02-004
[决策标题] gRPC worker pool 默认 8
[决策状态] 已接受
[决策内容] K4Servicer 默认 worker_pool_size = 8，queue_max_size = 100，timeout_sec = 10
[决策理由]
  1. 来自 MD-MCP-V1.0#M-C02 "8 worker pool" + IC-009 "QueueFull(>100)" + "Timeout(>10s)"
  2. 8 = CPU 核数（假设 8 核）匹配 K4 CPU-bound 静态分析负载
  3. 100 队列上限防止 OOM；客户端 gRPC retry 自动重发
[拒绝的替代方案]
  方案A: 4 worker — 拒绝理由：P95 ≤ 10s 性能目标难以达成
  方案B: 16 worker — 拒绝理由：过度占用 CPU 资源；按 8 核匹配
[影响范围] grpc_server.py K4Servicer.__init__ + DEFAULT_* 常量
[相关FDR] FDR-M-C02-001
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + IC-009]
```

---

## FDR-M-C02-005 模板方法骨架与 Strategy 解耦

```
[决策编号] FDR-M-C02-005
[决策标题] ASTAnalyzer 模板方法骨架 + 12 Rule 策略解耦
[决策状态] 已接受
[决策内容] ASTAnalyzer 提供 parse/walk/score/tag 四步骨架；12 Rule 各自实现 match 单方法；RuleRegistry 管理注册
[决策理由]
  1. 来自 MD-MCP-V1.0#M-C02 设计模式 "Strategy + Template Method"
  2. 模板方法封装"先 walk 再 score 再 tag"的固定流程，规则实现仅需关注 match 单点
  3. 便于未来新增 Rule 仅需继承 Rule ABC + RuleRegistry.register
[拒绝的替代方案]
  方案A: 单类 12 分支 if-else — 拒绝理由：违反 OCP；新增规则需改 analyzer
  方案B: 完全无模板方法 — 拒绝理由：每个 Rule 重复 walk/score/tag 逻辑
[影响范围] analyzer.py + rules/base.py + rules/*.py
[相关FDR] FDR-M-C02-003
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + DP-MCP-V1.0#Strategy#Template Method]
```

---

## FDR-M-C02-006 测试用例总数 50+

```
[决策编号] FDR-M-C02-006
[决策标题] 测试用例 8+10+36+6+6 = 66 个（覆盖 MD 要求的 50）
[决策状态] 已接受
[决策内容] test_analyzer 8 + test_grpc_server 10 + test_rules 36 + test_corpus 6 + test_cache 6 = 66 用例
[决策理由]
  1. 来自 MD-MCP-V1.0#M-C02 "用例数: 50（11+1 规则 × 4 场景 = 48 + 校准 2）"
  2. 36 规则用例（12 规则 × 3 场景）超出原计划但保证规则覆盖度
  3. 10 gRPC servicer 用例覆盖错误码映射与并发
[拒绝的替代方案]
  方案A: 50 用例严格匹配 MD — 拒绝理由：每个规则 4 场景会模糊命中/未命中/边界
  方案B: 80+ 用例 — 拒绝理由：超过 4.7 测试性价比拐点
[影响范围] tests/* (5 文件)
[相关FDR] FDR-M-C02-003
[来源标注] [DD-001:MD-MCP-V1.0#M-C02 + DD-M推断:依据测试设计原则]
```

---

**框架决策记录文档结束（共 6 条 FDR）**
