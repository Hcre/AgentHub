# 接口注释清单 API-M-C03-MCP-V1.0-20260602

> 模块: M-C03 Template Engine
> 关联 IC: IC-010 (template.upgrade → API-220)
> 唯一负责模块: M-C03
> 接口契约来源: [DD-001:IC-MCP-V1.0-20260602.md#IC-010]
> 注释覆盖率: 100% (1/1 IC + 1 in-proc IC-022 约束)

---

## API-001 顶层 merge 函数（IC-010 实现）

```
[接口编号] API-001-merge
[关联契约] IC-010 / API-220
[实现文件] src/agenthub/infrastructure/template/merger.py
[函数签名注释]
  ```python
  @pure
  @in_process_only
  def merge(
      base: Mapping[str, object],       # [基底层；必须可 JSON 序列化]
      override: Mapping[str, object],    # [覆盖层；必须可 JSON 序列化]
      max_depth: int = 10,              # [递归深度上限；1 ≤ max_depth ≤ 50]
      list_merge_strategy: str = "override",  # [∈ {"override","concat","unique_concat"}]
  ) -> dict[str, object]:               # [深合并结果；不修改入参]
      """
      深合并 base 与 override，返回新 dict（不修改入参）.

      Args:
          base: 模板基底；不可变入参；必须可 JSON 序列化
          override: 覆盖层；同 base 约束
          max_depth: 递归深度上限，默认 10
          list_merge_strategy: list 合并策略，默认 "override"

      Returns:
          深合并后的新 dict

      Raises:
          DepthLimitError: 递归深度超限（循环引用）
          TemplateValidationError: 合并结果不合法 schema
          ValueError: list_merge_strategy 非法

      Example:
          >>> merge({"a": 1}, {"b": 2})
          {'a': 1, 'b': 2}
      """
  ```
[参数说明] base / override / max_depth / list_merge_strategy - 同上
[返回值说明] dict[str, object] - 深合并结果；空输入返回空 dict
[错误码说明]
  TEMPLATE_CIRCULAR_REF 422 - 递归深度超限
  TEMPLATE_SCHEMA_VIOLATION 422 - 合并结果不合法 schema
[并发安全] 纯函数线程安全（无共享状态）
[幂等性] 是；同输入 → 同输出；永久
[性能约束] < 5ms（[DD-001:IC-010]）
[来源标注] [DD-001:IC-010 + AR:TS-030]
```

---

## API-002 顶层 validate 函数（IC-010 实现）

```
[接口编号] API-002-validate
[关联契约] IC-010 / API-220
[实现文件] src/agenthub/infrastructure/template/schema.py
[函数签名注释]
  ```python
  def validate(
      merged: Mapping[str, object],     # [合并后结果；可 JSON 序列化]
      schema: Mapping[str, object],     # [JSON Schema Draft 2020-12；顶层必须 dict；$id 必填]
  ) -> ValidationResult:                # [{valid: bool, errors: list[ValidationErrorItem]}]
      """
      对合并结果做 schema 校验.

      Args:
          merged: 合并后结果
          schema: JSON Schema (Draft 2020-12)

      Returns:
          ValidationResult: valid + errors

      Raises:
          无（校验失败体现在 ValidationResult.valid=False）

      Example:
          >>> r = validate({"name": "ok"}, {"type":"object","required":["name"]})
          >>> r.valid
          True
      """
  ```
[参数说明] merged / schema - 同上
[返回值说明] ValidationResult - 校验结果对象
[错误码说明]
  TEMPLATE_SCHEMA_VIOLATION 422 - 体现在 ValidationResult.errors
[并发安全] 纯函数线程安全
[幂等性] 是
[性能约束] < 5ms
[来源标注] [DD-001:IC-010 + CS-MCP-V1.0-20260602 §7 JSON Schema]
```

---

## API-003 TemplateMerger.merge 类方法（IC-010 实现）

```
[接口编号] API-003-template-merger-merge
[关联契约] IC-010
[实现文件] src/agenthub/infrastructure/template/merger.py
[函数签名注释]
  ```python
  class TemplateMerger:
      @staticmethod
      @pure
      @in_process_only
      def merge(
          base: Mapping[str, object],
          override: Mapping[str, object],
          max_depth: int = 10,
          list_merge_strategy: str = "override",
      ) -> dict[str, object]:
          """
          深合并入口，标量覆盖 + dict 递归 + list 按策略合并.

          （参数/返回/异常/性能 同顶层 merge，类方法为容器化封装）
          """
  ```
[参数说明] 同 API-001
[返回值说明] 同 API-001
[错误码说明] 同 API-001
[并发安全] 纯函数线程安全
[幂等性] 是
[性能约束] < 5ms
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:Value Object 容器化封装]
```

---

## API-004 TemplateMerger.merge_with_diff 类方法

```
[接口编号] API-004-template-merger-merge-with-diff
[关联契约] IC-010 (包含 diff 字段)
[实现文件] src/agenthub/infrastructure/template/merger.py
[函数签名注释]
  ```python
  class TemplateMerger:
      @staticmethod
      @pure
      @in_process_only
      def merge_with_diff(
          base: Mapping[str, object],
          override: Mapping[str, object],
          max_depth: int = 10,
          list_merge_strategy: str = "override",
      ) -> tuple[dict[str, object], list[dict[str, object]]]:
          """
          深合并 + diff 列表（jsondiff Patch 协议）.

          Returns:
              (merged, diff) - diff 每项为 {"op": str, "path": str, "value": Any}

          Raises:
              DepthLimitError / TemplateValidationError / ValueError
          """
  ```
[参数说明] 同 API-003
[返回值说明] (merged, diff) 元组；diff 为空当 base==override
[错误码说明] TEMPLATE_CIRCULAR_REF / TEMPLATE_SCHEMA_VIOLATION
[并发安全] 纯函数线程安全
[幂等性] 是
[性能约束] < 5ms
[来源标注] [DD-001:IC-010 + AR:TS-030]
```

---

## API-005 TemplateConfig 构造与不可变更新（IC-022 in-proc 约束）

```
[接口编号] API-005-template-config
[关联契约] IC-022 (in-proc 函数集合)
[实现文件] src/agenthub/infrastructure/template/schema.py
[函数签名注释]
  ```python
  class TemplateConfig(BaseModel):
      """模板配置 Value Object（frozen=True）."""
      model_config: ConfigDict = ConfigDict(frozen=True, extra="forbid")

      base: dict[str, object] = Field(default_factory=dict)
      override: dict[str, object] = Field(default_factory=dict)
      max_depth: int = Field(default=10, ge=1, le=50)
      list_merge_strategy: str = Field(default="override")

      def to_merged(self) -> dict[str, object]:
          """便捷：基于自身配置执行 merge."""

      def with_override(self, extra: dict[str, object]) -> TemplateConfig:
          """返回带额外 override 的新 TemplateConfig（frozen 不可 in-place 修改）."""
  ```
[参数说明] 构造参数见 Field 声明
[返回值说明] to_merged -> dict; with_override -> 新 TemplateConfig
[错误码说明] ValueError (Pydantic ValidationError) - 参数越界
[并发安全] 不可变对象线程安全
[幂等性] with_override: 是；to_merged: 是
[性能约束] 构造 O(1)；to_merged 同 merge < 5ms
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-C03 + DD-M推断:Value Object 范式]
```

---

## API-006 ValidationResult.raise_if_invalid

```
[接口编号] API-006-raise-if-invalid
[关联契约] IC-010
[实现文件] src/agenthub/infrastructure/template/schema.py
[函数签名注释]
  ```python
  class ValidationResult(BaseModel):
      valid: bool
      errors: list[ValidationErrorItem] = Field(default_factory=list)

      def raise_if_invalid(self) -> None:
          """失败时抛 TemplateValidationError；通过时无副作用."""
  ```
[参数说明] 无
[返回值说明] None
[错误码说明] 抛出时转译为 TEMPLATE_SCHEMA_VIOLATION
[并发安全] 线程安全
[幂等性] 是
[性能约束] O(1)
[来源标注] [DD-M推断:领域结果对象便捷方法]
```

---

## API 注释覆盖率统计

| 接口编号 | 关联 IC | 实现文件 | 函数签名 | 参数说明 | 返回值说明 | 错误码说明 | 状态 |
|----------|--------|----------|---------|---------|-----------|-----------|------|
| API-001-merge | IC-010 | merger.py | ✓ | ✓ | ✓ | ✓ | 完成 |
| API-002-validate | IC-010 | schema.py | ✓ | ✓ | ✓ | ✓ | 完成 |
| API-003-template-merger-merge | IC-010 | merger.py | ✓ | ✓ | ✓ | ✓ | 完成 |
| API-004-template-merger-merge-with-diff | IC-010 | merger.py | ✓ | ✓ | ✓ | ✓ | 完成 |
| API-005-template-config | IC-022 | schema.py | ✓ | ✓ | ✓ | ✓ | 完成 |
| API-006-raise-if-invalid | IC-010 | schema.py | ✓ | ✓ | ✓ | ✓ | 完成 |

**D4 接口契约注释化完整度 = 100% (6/6)**

---

[来源标注] [DD-001:IC-010 + DD-M推断:补充顶层函数与类方法的函数签名注释]
