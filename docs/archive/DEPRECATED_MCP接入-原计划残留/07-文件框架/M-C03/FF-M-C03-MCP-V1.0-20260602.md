# 文件框架结构 FF-M-C03-MCP-V1.0-20260602

> 模块: M-C03 Template Engine
> 项目代号: MCP
> 版本: V1.0
> 日期: 2026-06-02
> 角色: DD-M-12 详细设计师（模块）
> 上游: DD-001 (DDI = 0.952 ≥ 0.90 通过)
> 下游: DD-S 结构设计师
> 唯一负责模块: M-C03

---

## 1. 文件框架结构

```
[模块编号] M-C03
[模块名称] Template Engine
[文件框架]
  产出物/07-文件框架/M-C03/
  └── src/
      └── agenthub/
          └── infrastructure/
              └── template/
                  ├── __init__.py        ← [职责: 模块初始化与公共符号导出]
                  ├── merger.py          ← [职责: TemplateMerger 纯函数容器 + merge/validate 顶层函数]
                  │     - [TemplateMerger 类注释 - 纯函数容器]
                  │     - [TemplateMerger.merge 注释 - 深合并入口]
                  │     - [TemplateMerger.merge_with_diff 注释 - 合并 + diff]
                  │     - [TemplateMerger.validate 注释 - schema 校验]
                  │     - [merge 顶层函数注释 - 便捷调用]
                  │     - [validate 顶层函数注释 - 便捷调用]
                  │     - [DEFAULT_MAX_DEPTH / DEFAULT_LIST_MERGE_STRATEGY / DEFAULT_TEMPLATE_PROFILE 常量注释]
                  ├── schema.py          ← [职责: Value Object + 领域异常 + 顶层 validate]
                  │     - [TemplateConfig 类注释 - frozen Value Object]
                  │     - [TemplateConfig.__post_init_post_parse__ 注释 - 策略白名单校验]
                  │     - [TemplateConfig.to_merged 注释 - 便捷合并]
                  │     - [TemplateConfig.with_override 注释 - 不可变更新]
                  │     - [ValidationErrorItem 类注释 - 错误载体]
                  │     - [ValidationResult 类注释 - 校验结果]
                  │     - [ValidationResult.raise_if_invalid 注释 - 失败抛出]
                  │     - [TemplateValidationError 类注释 - 领域异常]
                  │     - [TemplateValidationError.__init__ 注释 - 构造]
                  │     - [TemplateValidationError.to_code 注释 - 错误码]
                  │     - [DepthLimitError 类注释 - 循环引用异常]
                  │     - [DepthLimitError.__init__ 注释 - 构造]
                  │     - [DepthLimitError.to_code 注释 - 错误码]
                  │     - [validate 顶层函数注释 - schema 校验入口]
                  │     - [ALLOWED_LIST_MERGE_STRATEGIES / MIN_MAX_DEPTH / MAX_MAX_DEPTH / DEFAULT_MAX_DEPTH_VALUE 常量注释]
                  └── tests/
                      ├── __init__.py    ← [职责: pytest 集中 fixture 声明]
                      │     - [sample_base / sample_override / sample_schema / frozen_mutation_guard fixtures]
                      ├── test_merger.py ← [职责: TemplateMerger 单元测试]
                      │     - [测试场景1: 标量覆盖]
                      │     - [测试场景2: dict 递归合并]
                      │     - [测试场景3: list 默认 override]
                      │     - [测试场景4: list concat 策略]
                      │     - [测试场景5: 顶层函数等价]
                      │     - [测试场景6: diff 输出]
                      │     - [测试场景7: diff 空]
                      │     - [测试场景8: 不可变性]
                      │     - [测试场景9: 性能 < 5ms]
                      │     - [测试场景10: 循环引用]
                      │     - [测试场景11: max_depth=1 边界]
                      │     - [测试场景12: 非法 list 策略]
                      │     - [测试场景13: DEFAULT_MAX_DEPTH 常量]
                      │     - [测试场景14: validate 委托]
                      └── test_schema.py  ← [职责: TemplateConfig / ValidationResult / 领域异常单元测试]
                            - [测试场景1: 默认配置]
                            - [测试场景2: frozen 不可变]
                            - [测试场景3: with_override 新实例]
                            - [测试场景4: validate 成功]
                            - [测试场景5: validate 失败]
                            - [测试场景6: raise_if_invalid 抛出]
                            - [测试场景7: raise_if_invalid 通过]
                            - [测试场景8: TemplateValidationError.to_code]
                            - [测试场景9: DepthLimitError.to_code]
                            - [测试场景10: ALLOWED 白名单]
                            - [测试场景11: MIN/MAX 常量]
                            - [测试场景12: max_depth 越界]
                            - [测试场景13: list 策略非法]

[文件间依赖关系]
  tests/test_merger.py → merger.py → schema.py → core.exceptions (AgentHubError)
  tests/test_schema.py → schema.py → core.exceptions
  tests/__init__.py   → (无依赖，提供 fixtures)
  __init__.py         → merger.py + schema.py

[命名合规] snake_case 文件 / PascalCase 类 / UPPER_SNAKE_CASE 常量 / 全部通过 [CS §1.1]
[FastAPI 最佳实践] ✓ src-layout + 子包化
[来源标注] [DD-001:FS-012 / MD-MCP-V1.0-20260602.md#M-C03 / IC-010 + DD-M推断:遵循 [DD-001:DD洞察-2] 强制 in-proc]
```

---

## 2. 文件清单与状态

| 文件路径 | 文件头注释 | 类/函数注释 | 注释完整度 | 状态 |
|----------|----------|------------|----------|------|
| `src/agenthub/infrastructure/template/__init__.py` | 有 | 公共符号导出 | 100% | 完成 |
| `src/agenthub/infrastructure/template/merger.py` | 有 | 1 类 + 6 函数/方法 + 3 常量 | 100% | 完成 |
| `src/agenthub/infrastructure/template/schema.py` | 有 | 4 类 + 10 函数/方法 + 4 常量 | 100% | 完成 |
| `src/agenthub/infrastructure/template/tests/__init__.py` | 有 | 4 fixtures | 100% | 完成 |
| `src/agenthub/infrastructure/template/tests/test_merger.py` | 有 | 14 测试场景 | 100% | 完成 |
| `src/agenthub/infrastructure/template/tests/test_schema.py` | 有 | 13 测试场景 | 100% | 完成 |

总计 6 个文件，37 个测试场景，4 个领域类，4 个 fixture，3 个纯函数/便捷函数入口。

---

## 3. 文件结构合规 5 项检查（soul 4.7）

| 检查项 | 通过情况 | 证据 |
|--------|--------|------|
| 目录层级 ≥ 2 | ✓ | `src/agenthub/infrastructure/template/` = 5 层 |
| 文件命名合规 | ✓ | snake_case (`merger.py`, `schema.py`, `test_merger.py`, `test_schema.py`) |
| 文件职责单一 | ✓ | merger=纯函数容器 / schema=Value Object + 异常 / __init__=导出 / tests=测试 |
| 依赖关系无循环 | ✓ | 依赖方向: tests → merger → schema → core.exceptions (无回环) |
| 最佳实践 | ✓ | src-layout + 子包化 + `__init__.py` 存在 + tests 独立子包 |

合规度: **5/5 通过 = 高** (soul 4.7)

---

## 4. 多方案对比（soul 4.11，6 维度）

| 维度 | 权重 | 主方案 A：merger.py + schema.py（单文件 + 单文件） | 备选方案 B：merge/ + override/ + validate/ 三子包 | A 得分 | B 得分 |
|------|------|---------|---------|------|------|
| 文件结构合规度 | 0.22 | 高（5/5 项通过） | 中（子包边界增加引入循环风险） | 9 | 7 |
| 注释完整度 | 0.22 | 高（100% 覆盖） | 中（子包间接口需要更多注释） | 9 | 7 |
| 接口契约注释化完整度 | 0.18 | 高（IC-010 完全体现） | 中（IC-010 跨子包需重复） | 9 | 7 |
| 代码风格合规度 | 0.13 | 高（snake_case 100%） | 中（子包名/文件名易冲突） | 9 | 8 |
| 设计可追溯性 | 0.13 | 高（100% 来源标注） | 中（子包层级深，来源标注路径长） | 9 | 7 |
| 文件框架可追溯性 | 0.12 | 高（6 个文件清晰） | 中（6+ 个文件分散） | 9 | 7 |
| **加权总分** | 1.00 | | | **9.00** | **7.10** |

**[选择理由]**
主方案 A 严格遵循 [DD-001:FS-012]（该规范明确 `merger.py` + `schema.py` + `tests/` 三层结构），与上游设计规范一致性最高。备选方案 B 将 [DD-001:MD-MCP-V1.0-20260602.md#M-C03] 的 merge/override/validate 三子模块字面化为子包，但 M-C03 为纯函数 in-proc 模块，过度拆分会引入不必要的包级间接和潜在循环依赖风险（违反 R14 禁止过度拆分）。加权差 1.90，原始 100 分制差值 19 ≥ 5（soul 4.11 阈值），主方案显著胜出。

---

## 5. 框架决策记录

详见 `FDR-M-C03-MCP-V1.0-20260602.md`。

---

## 6. 文件框架健康度仪表盘

详见 `FH-M-C03-MCP-V1.0-20260602.md`。

---

**[DD-M 洞察-1]** M-C03 在 [DD-001:DD洞察-2] 中被识别为"纯函数 in-proc"高风险模块——若未来被错误重构为远程服务，< 5ms 性能约束会立即破坏。本框架通过 `@pure` + `@in_process_only` 双装饰器在静态层面固化这一约束，使 CI 可用 grep 检查禁字符（`await`/`open(`/`requests`/`asyncio`/`subprocess`），约束可被强制执行。

**[DD-M 洞察-2]** TemplateConfig 选用 `frozen=True` + `ConfigDict(extra="forbid")` 是 Pydantic v2 中"严格不可变 Value Object"的标准做法，但需要在测试侧显式添加 `frozen_mutation_guard` fixture（已在 tests/__init__.py 占位）以提醒测试人员不可 in-place 修改。建议下游 DD-S 在 model_dump 路径中增加 freeze 单元测试。

**[文件框架交付]** 已就绪，等待 DD-S 骨架搭建。

[来源标注] [DD-001:FS-012/MD-MCP-V1.0-20260602.md#M-C03/IC-010 + DD-M推断:FS-012 与 MD 子模块拆分语义的协调]
