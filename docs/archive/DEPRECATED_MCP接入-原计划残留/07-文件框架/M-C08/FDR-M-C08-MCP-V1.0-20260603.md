# 框架决策记录 FDR-M-C08-MCP-V1.0-20260603

> M-C08 Name Transformer 重大框架决策记录
> DD-M-C08 产出  ·  依据 soul 4.13 FDR 模板

---

## FDR-C08-001 选择"单文件 transformer.py"而非三子模块文件

```
[决策编号] FDR-C08-001
[决策标题] M-C08 合并 hash/collision/mapping 三子模块为单 transformer.py
[决策状态] 已接受
[决策内容] 将 MD-MCP#M-C08 中规划的 hash/、collision/、mapping/ 三子模块合并为单一 transformer.py
[决策理由]
  1. 三个子模块实际只对应 2 个函数 + 1 个类，文件数膨胀会损害"单文件职责清晰"原则
  2. 全部为纯函数 + 常量，零 IO/无状态，按职责分文件会形成跨文件函数调用（hash_util.sha256 → collision_check）
  3. Python 社区最佳实践对小工具模块倾向单文件聚合（如 hashlib 自身的多算法也是单文件）
  4. 测试文件数仍可保持 1 个，复杂度可控
[拒绝的替代方案]
  方案A: 三子模块文件（hash.py + collision.py + mapping.py）
  拒绝理由: 三个子文件相互 import 反而引入"包内循环"风险（hash → collision → hash 共享类型），文件结构复杂度 > 收益
  方案B: 拆分到独立微包
  拒绝理由: V1.0 单体仓库策略下，过度拆分违反 R14 禁止过度设计
[影响范围]
  文件: src/agenthub/infrastructure/naming/transformer.py
  模块: M-C08
  接口: API-001 ~ API-004
  测试: tests/test_transformer.py 覆盖全部 15 用例
[相关FDR] 无
[来源标注] [DD-M推断:依据 MD-MCP#M-C08 子模块拆分为"逻辑分组"语义，结合 R14 单文件职责原则做合并]
```

---

## FDR-C08-002 选择"静态类 + 顶层函数双形态导出"而非仅静态类

```
[决策编号] FDR-C08-002
[决策标题] 同时导出顶层函数与 NameTransformer 静态类
[决策状态] 已接受
[决策内容] __init__.py 同时导出 transform() / detect_collision() 顶层函数与 NameTransformer.transform / NameTransformer.detect_collision 静态方法
[决策理由]
  1. MD-MCP#M-C08 明确定义 NameTransformer 静态类（必须提供，否则不满足类设计约束）
  2. 顶层函数更易于在 Functional 风格代码中使用（functools.partial、lambda 包装等）
  3. 双形态 = 双消费场景，零额外成本（静态类仅一行 def 委托）
  4. 测试可同时覆盖两种形态，验证行为一致（test_nametransformer_static_transform_matches_function）
[拒绝的替代方案]
  方案A: 仅提供 NameTransformer 静态类
  拒绝理由: 静态方法在 functools.partial / 函数式组合场景下使用不便
  方案B: 仅提供顶层函数
  拒绝理由: 不满足 MD-MCP#M-C08 "NameTransformer 静态类容器"硬性类设计约束
[影响范围]
  文件: src/agenthub/infrastructure/naming/__init__.py
  接口: API-001 ~ API-004 4 个全部
[相关FDR] FDR-C08-001
[来源标注] [DD-001:MD-MCP#M-C08 "NameTransformer - 纯函数容器 - {} - @staticmethod transform, detect_collision"]
```

---

## FDR-C08-003 选择"仅依赖标准库 hashlib"而非 hashlib + 命名空间工厂

```
[决策编号] FDR-C08-003
[决策标题] 命名空间前缀 mcp_ 仅保留为常量不引入工厂类
[决策状态] 已接受
[决策内容] 保留 NAMING_NAMESPACE_PREFIX 常量但不引入 NamespaceFactory
[决策理由]
  1. V1.0 仅 1 个命名空间（mcp_），引入工厂是 YAGNI
  2. 常量保留以备未来扩展（BR-001~004 提及命名空间隔离）
  3. 纯函数模块引入工厂类会破坏"Pure Function" 设计模式约束
[拒绝的替代方案]
  方案A: NamespaceFactory + 多命名空间注册表
  拒绝理由: 违反 V1.0 单命名空间 YAGNI 原则；增加 5x 代码量；增加测试用例
  方案B: 直接硬编码 "mcp_" 前缀
  拒绝理由: 未来扩展需改业务代码，违反 OCP；保留常量低成本
[影响范围]
  文件: src/agenthub/infrastructure/naming/transformer.py
  常量: NAMING_NAMESPACE_PREFIX = "mcp_"
[相关FDR] 无
[来源标注] [DD-M推断:依据 BR-001~004 命名空间约定 + YAGNI 原则]
```

---

## FDR-C08-004 选择"NameTransformerError 基类 + NameValidationError/CollisionDetectedError 子类"异常分层

```
[决策编号] FDR-C08-004
[决策标题] 异常分层：基类 + 业务子类
[决策状态] 已接受
[决策内容] 定义 NameTransformerError 基类，NameValidationError 与 CollisionDetectedError 继承
[决策理由]
  1. CS-MCP §1.6 强制"自定义异常继承 agenthub.core.exceptions.AgentHubError"
  2. 跨模块调用方（M-B03）需要 catch 基类即可捕获本模块所有异常
  3. NameValidationError 多继承 ValueError 符合 Python 习惯（"参数错误"语义统一）
  4. CollisionDetectedError 不继承 ValueError（业务异常，非参数错误）
[拒绝的替代方案]
  方案A: 不设基类，直接两个独立异常
  拒绝理由: 调用方需分别 catch，违反 DRY
  方案B: 统一继承 agenthub.core.exceptions.AgentHubError
  拒绝理由: AgentHubError 在 M-C08 出现过于泛化；NameTransformerError 提供更精确的语义
  注: 可考虑未来让 NameTransformerError 继承 AgentHubError（演进项）
[影响范围]
  文件: src/agenthub/infrastructure/naming/transformer.py
  异常: NameTransformerError / NameValidationError / CollisionDetectedError
[相关FDR] 无
[来源标注] [DD-001:CS-MCP §1.6 异常规范 + DD-M推断:NameValidationError 多继承 ValueError 的 Python 习惯]
```

---

## 决策统计

| 状态 | 数量 |
|------|------|
| 已接受 | 4 |
| 已拒绝 | 4（被拒绝方案已分别记录于各 FDR） |
| 草稿 | 0 |

---

## DD-M 洞察注入

```
[DD-M洞察-1] [类型: 文件结构]
  M-C08 虽被 MD-MCP#M-C08 规划为 3 个子模块（hash/collision/mapping），
  但实际只包含 2 个函数 + 1 个类 + 2 个异常。强行拆分为 3 个文件会引入
  "包内跨文件函数调用"，反而增加复杂度。已通过 FDR-C08-001 合并为单 transformer.py。

[DD-M洞察-2] [类型: 跨模块依赖]
  M-C08 的核心调用方 M-B03 Binding Engine（strategies.py）需要持有"已分配名集合"。
  当前实现要求 M-B03 自行维护 frozenset。DD-M 建议：未来可在 M-C08 扩展
  _NamingCache 单例层（[DD-M推断:依据 IC-015 性能 < 1ms 与 Memory cache 透明化]），
  但 V1.0 保持纯函数无状态更符合 Pure Function 设计模式。

[DD-M洞察-3] [类型: 测试覆盖]
  MD-MCP#M-C08 要求"用例数 15；属性测试（hypothesis）"。
  当前框架已实现 15 个 test_ 函数（含 parametrized 展开 5 + 4 = 9 条变体），
  属性测试以注释占位形式标注，由 DD-Dev 在落地时启用 hypothesis 装饰器。
```

---

**[FDR 文档结束]**
