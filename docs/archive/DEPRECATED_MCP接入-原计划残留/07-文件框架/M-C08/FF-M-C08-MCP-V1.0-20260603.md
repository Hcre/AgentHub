# 文件框架结构 FF-M-C08-MCP-V1.0-20260603

> 模块 M-C08 Name Transformer 文件框架结构（仅注释，无业务代码）
> DD-M-C08 产出  ·  来源 [DD-001:FS-017/MD-MCP#M-C08/IC-015]

---

## 0. 模块概览

| 字段 | 值 |
|------|-----|
| 模块编号 | M-C08 |
| 模块名称 | Name Transformer |
| 负责 DD-M | DD-M-C08（agent-dd-module-designer-M-C08） |
| 设计模式 | Pure Function（无 IO，无状态） |
| 关联 IC | IC-015（name.transform） |
| 关联 API | API-270（name.transform） |
| 关联技术选型 | TS-标准库 hashlib（无三方依赖） |
| 关联 ADR | ADR-007（6→8 字符 hex 升级） |
| 关联 BR | BR-001~004 |
| 依赖方向 | 被 M-B03 Binding Engine 调用；不依赖任何项目内模块（除 core.pure 装饰器） |

---

## 1. 目录结构与文件清单

```
产出物/07-文件框架/M-C08/
└── src/
    └── agenthub/
        └── infrastructure/
            └── naming/
                ├── __init__.py                      ← [文件0：模块门面，导出 transform / detect_collision / NameTransformer / 异常 / 常量]
                ├── transformer.py                   ← [文件1：纯函数实现 + 静态类容器]
                └── tests/
                    ├── __init__.py                  ← [测试包初始化]
                    └── test_transformer.py          ← [文件2：单元测试（15 用例 + hypothesis 占位）]
```

---

## 2. 文件职责矩阵

| 文件路径 | 职责 | 行数估算 | 包含元素 |
|---------|------|---------|---------|
| `src/agenthub/infrastructure/naming/__init__.py` | 模块门面，统一导出公共 API | ~30 | 5 个 export（函数2 + 类1 + 异常2 + 常量 5 → 合并为 1 行 from import） |
| `src/agenthub/infrastructure/naming/transformer.py` | 纯函数 transform / detect_collision + 静态类容器 + 异常类型 + 常量 | ~150 | 2 个函数 + 1 个类 + 2 个异常 + 5 个常量 |
| `src/agenthub/infrastructure/naming/tests/__init__.py` | 测试包标记 | ~5 | 空 docstring |
| `src/agenthub/infrastructure/naming/tests/test_transformer.py` | 15 用例覆盖（核心 8 / 边界 4 / 异常 3） + hypothesis 占位 | ~200 | 15 个 test_ 函数 + 1 个注释占位 |

**文件数：4**（2 个生产 + 2 个测试），符合 soul 4.2 单模块文件数范围 [3, 8]。

---

## 3. 文件间依赖关系

```
__init__.py
    └─→ transformer.py
              ├─→ core.pure（@pure / @in_process_only 装饰器）  [CS-MCP §1.9]
              └─→ 标准库 hashlib                                [零三方依赖]

tests/test_transformer.py
    └─→ transformer.py (NameTransformer / transform / detect_collision / 异常 / 常量)
    └─→ pytest                                                  [CS-MCP §1.7]
```

**无循环依赖**（R26）。**无跨模块依赖**（R28/D7=100）。

---

## 4. 模块边界守护（D7=100）

| 检查项 | 状态 |
|--------|------|
| 负责模块 | 仅 M-C08 |
| 操作文件列表 | 产出物/07-文件框架/M-C08/ 下的 4 个文件 |
| 跨模块文件数 | 0 |
| 跨模块引用 | 0（仅引用 core.pure，core 为横切层，所有模块均可使用） |
| D7 模块边界遵守度 | 100% |

**核心引用说明：** `agenthub.core.pure` 为 CS-MCP §1.9 定义的横切装饰器模块（[DD-001] 明确规划），并非其他业务模块——不构成跨模块业务依赖。

---

## 5. 来源标注

| 文件 | 主要来源 |
|------|---------|
| `transformer.py` | [DD-001:FS-017] 文件结构 / [DD-001:MD-MCP#M-C08] 类设计 / [DD-001:IC-015/API-270] 接口契约 / [DD-001:ADR-007] 升级规则 / [DD-001:CS-MCP §1.9] 装饰器约束 |
| `__init__.py` | [DD-001:FS-017] 文件清单 / [DD-M推断:门面聚合] |
| `tests/test_transformer.py` | [DD-001:MD-MCP#M-C08] "用例数 15；属性测试（hypothesis）" / [DD-001:CS-MCP §1.7] 测试规范 |
| `tests/__init__.py` | [DD-001:FS-017] tests/ 目录约定 |

---

## 6. 文件命名合规（FS-017 + CS-MCP §1.1）

| 文件 | 命名 | 合规 |
|------|------|------|
| `__init__.py` | Python 包标识 | ✓ |
| `transformer.py` | snake_case 模块文件 | ✓ |
| `tests/__init__.py` | Python 测试包子包 | ✓ |
| `tests/test_transformer.py` | `test_{feature}.py` 规范 | ✓ |

---

**[FF 文档结束]**
