# 框架决策记录 FDR-M-C03-MCP-V1.0-20260602

> 模块: M-C03 Template Engine
> 唯一负责模块: M-C03
> 决策数量: 6
> 状态: 全部已接受

---

## FDR-001 选定单文件 merger.py + schema.py 而非三子包

```
[决策编号] FDR-001
[决策标题] M-C03 选 FS-012 风格的 merger.py + schema.py
[决策状态] 已接受
[决策内容] 按 [DD-001:FS-012] 定义，将 merge/override/validate 三子模块逻辑合并到 merger.py + schema.py 两个文件，不创建子包
[决策理由]
  - 严格遵循上游 FS-012 规范（已通过 DDI=0.952 评审）
  - M-C03 为纯函数 in-proc 模块，函数总量 < 20，单文件即可承载
  - 避免三子包引入不必要的包级间接与潜在循环依赖
  - 性能 < 5ms 约束下，减少函数调用层级
[拒绝的替代方案]
  - 备选 B: merge/ + override/ + validate/ 三子包（[DD-001:MD-MCP-V1.0-20260602.md#M-C03] 字面化）
  - 拒绝理由: 与 FS-012 冲突；引入包级间接；R14 禁止过度拆分
[影响范围] src/agenthub/infrastructure/template/merger.py + schema.py
[相关FDR] FDR-002
[来源标注] [DD-001:FS-012 + DD-M推断:依据 soul 4.7 + 4.11]
```

---

## FDR-002 采用 @pure + @in_process_only 双装饰器

```
[决策编号] FDR-002
[决策标题] 强制 in-proc 约束采用双装饰器
[决策状态] 已接受
[决策内容] 为顶层 merge / validate 与类方法 TemplateMerger.merge/merge_with_diff/validate 标注 @pure（来自 agenthub.core.pure）+ @in_process_only
[决策理由]
  - 响应 [DD-001:DD洞察-2]：M-C03 误重构为远程服务将导致性能从 < 5ms 退化到 50ms+
  - 装饰器可在 CI 静态检查（grep 禁字符）
  - 与 [DD-001:CS-MCP-V1.0-20260602 §1.9] 装饰器规范一致
[拒绝的替代方案]
  - 备选 B: 仅用文档说明 in-proc
  - 拒绝理由: 文档易忽略，CI 无法自动检查
[影响范围] merger.py 全部公共函数
[相关FDR] FDR-001
[来源标注] [DD-001:DD洞察-2 + CS-MCP-V1.0-20260602 §1.9]
```

---

## FDR-003 TemplateConfig 采用 Pydantic frozen=True Value Object

```
[决策编号] FDR-003
[决策标题] TemplateConfig 不可变 + 严格字段
[决策状态] 已接受
[决策内容] TemplateConfig 继承 BaseModel + ConfigDict(frozen=True, extra="forbid")；max_depth 字段用 Field(ge=1, le=50) 限制
[决策理由]
  - Value Object 范式：不可变 + 严格字段是 in-proc 配置的标准做法
  - frozen 保证线程安全与不可变性断言
  - extra="forbid" 防止未声明字段污染配置
  - 便于 Pydantic 自动校验与序列化
[拒绝的替代方案]
  - 备选 B: 普通 @dataclass
  - 拒绝理由: 缺乏类型校验与自动序列化；与 CS §1.3 类型注解要求兼容性弱
  - 备选 C: 嵌套 dict
  - 拒绝理由: 无类型保证；运行时错误
[影响范围] schema.py
[相关FDR] FDR-001
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:Pydantic v2 frozen 实践]
```

---

## FDR-004 错误码统一通过 to_code() 方法暴露

```
[决策编号] FDR-004
[决策标题] 领域异常的 IC 错误码暴露方式
[决策状态] 已接受
[决策内容] TemplateValidationError / DepthLimitError 各自提供 to_code() 方法，返回 IC-010 错误码常量字符串
[决策理由]
  - 错误码集中定义在 IC-010，避免散落字符串
  - 易于测试（直接断言 to_code() 返回值）
  - 易于调用方转译为 HTTP 状态码
[拒绝的替代方案]
  - 备选 B: 错误码作为异常类常量
  - 拒绝理由: 与 IC 关联弱；调用方需 import 异常类才能取码
[影响范围] schema.py
[相关FDR] -
[来源标注] [DD-001:IC-010 错误码字段 + DD-M推断:to_code 范式]
```

---

## FDR-005 顶层 merge / validate 函数与类方法并存

```
[决策编号] FDR-005
[决策标题] 暴露顶层便捷函数 + 类方法封装
[决策状态] 已接受
[决策内容] 同时提供顶层 merge() / validate() 函数（[DD-001:IC-010] 函数签名）和 TemplateMerger 类方法
[决策理由]
  - 顶层函数对齐 IC-010 函数签名（in-proc 调用方最简路径）
  - 类方法承载 Value Object 容器化风格（便于未来扩展命名空间）
  - 测试 5 已验证两者等价
[拒绝的替代方案]
  - 备选 B: 仅保留类方法
  - 拒绝理由: 调用方需 TemplateMerger.merge(...) 多一层前缀，与 IC-010 函数签名不一致
[影响范围] merger.py
[相关FDR] FDR-001
[来源标注] [DD-001:IC-010 函数签名 + DD-M推断:双重暴露]
```

---

## FDR-006 测试命名遵循 test_{function}_when_{scenario}_then_{expected}

```
[决策编号] FDR-006
[决策标题] 测试函数命名规范
[决策状态] 已接受
[决策内容] 所有测试函数采用 [CS §1.7] 命名模板；测试体内 AAA 注释（given/when/then）
[决策理由]
  - 与 CS §1.7 完全一致，CI ruff D 规则自动检查
  - 命名即文档，新人 30 秒理解测试意图
  - AAA 注释便于阅读与重构
[拒绝的替代方案]
  - 备选 B: test_001 / test_002
  - 拒绝理由: 名称无语义；违反 CS §1.7
[影响范围] tests/test_merger.py + tests/test_schema.py
[相关FDR] -
[来源标注] [DD-001:CS-MCP-V1.0-20260602 §1.7 + DD-M推断:测试命名实践]
```

---

## 决策汇总

| FDR | 标题 | 状态 | 影响范围 |
|-----|------|------|----------|
| FDR-001 | merger.py + schema.py 而非三子包 | 已接受 | merger.py / schema.py |
| FDR-002 | @pure + @in_process_only 双装饰器 | 已接受 | merger.py 公共函数 |
| FDR-003 | Pydantic frozen=True Value Object | 已接受 | schema.py |
| FDR-004 | 错误码 to_code() 方法 | 已接受 | schema.py 异常类 |
| FDR-005 | 顶层函数 + 类方法并存 | 已接受 | merger.py |
| FDR-006 | 测试命名规范 | 已接受 | tests/ |

---

**[框架决策记录结束]**

[来源标注] [DD-001 全部 FS-012/MD/IC 引用 + DD-M推断:6 项关键框架决策]
