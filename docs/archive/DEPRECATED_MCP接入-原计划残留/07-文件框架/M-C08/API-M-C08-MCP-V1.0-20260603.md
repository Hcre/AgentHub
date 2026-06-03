# 接口注释清单 API-M-C08-MCP-V1.0-20260603

> M-C08 Name Transformer 接口契约注释化清单
> DD-M-C08 产出  ·  来源 [DD-001:IC-015/API-270/IC-022]

---

## API-001 IC-015 name.transform（顶层函数）

```
[接口编号] API-001
[关联契约] IC-015（来自 DD-001） + IC-022（in-proc 内部接口）
[关联 API 规范] API-270
[实现文件] src/agenthub/infrastructure/naming/transformer.py
[函数签名注释]
  ```python
  @pure
  @in_process_only
  def transform(name: str, length: int = DEFAULT_LENGTH) -> str:
      """名称 6→8 字符 hex 转换.

      Args:
          name: 原始 mcp 名称（非空字符串，建议调用前 strip）
          length: 输出长度，默认 6（碰撞场景下由调用方循环升 8/10/...）

      Returns:
          长度 == length 的小写 hex 串（SHA256(name).hexdigest()[:length]）

      Raises:
          NameValidationError: name 非 str / 空串 / length 越界 [4, 64]

      Example:
          >>> transform("mcp-foo")
          'a1b2c3'   # 6 字符 hex
      """
  ```
[参数说明]
  - name: str 必填；非空；UTF-8 可编码（hashlib 内置 UTF-8 编码）
  - length: int 可选=6；范围 [MIN_LENGTH=4, MAX_LENGTH=64]
[返回值说明]
  - 类型: str
  - 含义: SHA256(name) 的 hexdigest 前 N 位（小写）
  - 特殊值: 无（入参非法抛异常）
[错误码说明]
  - NameValidationError (ValueError 子类): 入参校验失败
[来源标注] [DD-001:IC-015/API-270/MD-MCP#M-C08 + CS-MCP §1.9 @pure 约束]
```

---

## API-002 IC-015 name.detect_collision（顶层函数）

```
[接口编号] API-002
[关联契约] IC-015 + IC-022
[关联 API 规范] API-270
[实现文件] src/agenthub/infrastructure/naming/transformer.py
[函数签名注释]
  ```python
  @pure
  @in_process_only
  def detect_collision(existing: frozenset[str], new: str) -> bool:
      """碰撞检测 —— 判定 new 是否与 existing 集合冲突.

      Args:
          existing: 已存在名称的不可变集合
          new: 待检测的新名称（非空字符串）

      Returns:
          True 表示 new ∈ existing（碰撞），False 表示无冲突

      Raises:
          NameValidationError: existing 非 frozenset / 元素非 str / new 非 str 或空

      Example:
          >>> detect_collision(frozenset({"a1b2c3"}), "a1b2c3")
          True
      """
  ```
[参数说明]
  - existing: frozenset[str] 必填；元素必须为 str
  - new: str 必填；非空
[返回值说明]
  - 类型: bool
  - 含义: new ∈ existing 的判定
  - 特殊值: 空 existing 永远返回 False
[错误码说明]
  - NameValidationError: 类型非法
[来源标注] [DD-001:IC-015/MD-MCP#M-C08 detect_collision 签名]
```

---

## API-003 IC-022 NameTransformer.transform（静态方法包装）

```
[接口编号] API-003
[关联契约] IC-022（in-proc 内部接口）
[关联 API 规范] API-270（门面变体）
[实现文件] src/agenthub/infrastructure/naming/transformer.py
[函数签名注释]
  ```python
  class NameTransformer:
      """Name Transformer 静态类容器（纯函数命名空间）."""

      @staticmethod
      @pure
      @in_process_only
      def transform(name: str, length: int = DEFAULT_LENGTH) -> str:
          """静态方法包装 —— 等价于顶层 transform() 函数.

          [来源标注] [DD-001:MD-MCP#M-C08 @staticmethod transform]
          """
  ```
[参数说明] 同 API-001
[返回值说明] 同 API-001
[错误码说明] 同 API-001
[来源标注] [DD-001:MD-MCP#M-C08 "NameTransformer - 纯函数容器 - {} - @staticmethod transform"]
```

---

## API-004 IC-022 NameTransformer.detect_collision（静态方法包装）

```
[接口编号] API-004
[关联契约] IC-022
[关联 API 规范] API-270（门面变体）
[实现文件] src/agenthub/infrastructure/naming/transformer.py
[函数签名注释]
  ```python
  class NameTransformer:
      @staticmethod
      @pure
      @in_process_only
      def detect_collision(existing: frozenset[str], new: str) -> bool:
          """静态方法包装 —— 等价于顶层 detect_collision() 函数.

          [来源标注] [DD-001:MD-MCP#M-C08 @staticmethod detect_collision]
          """
  ```
[参数说明] 同 API-002
[返回值说明] 同 API-002
[错误码说明] 同 API-002
[来源标注] [DD-001:MD-MCP#M-C08 "NameTransformer - 纯函数容器"]
```

---

## 接口覆盖度统计

| 维度 | 数量 | 覆盖率 |
|------|------|-------|
| DD-001 IC 引用 | 2（IC-015 显式 + IC-022 隐式） | 100% |
| 实际实现 API | 4（2 顶层函数 + 2 静态方法包装） | 100% |
| 入参注释完整 | 4/4 | 100% |
| 返回值注释完整 | 4/4 | 100% |
| 错误码注释完整 | 4/4（仅 transform 系含 NameValidationError；detect_collision 同样含，已在 API-002 体现） | 100% |

**D4 接口契约注释化完整度 = 100%**

---

**[API 文档结束]**
