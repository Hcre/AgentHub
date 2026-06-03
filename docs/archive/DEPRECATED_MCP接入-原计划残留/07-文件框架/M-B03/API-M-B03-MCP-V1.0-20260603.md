# 接口注释清单 API-M-B03-MCP-V1.0-20260603

> M-B03 Binding Engine 接口契约注释化清单
> 来源 [DD-001:IC-022 + API-120/121/122 + MD-MCP-V1.0-20260602#M-B03]

---

## API-001 bind（POST /bindings）

```
[接口编号] API-001
[关联契约] IC-022（in-proc 调用，外部走 API-120）
[实现文件] src/agenthub/application/binding/services.py
[函数签名注释]
  async def bind(
      ws_id: UUID,         # 工作区 ID
      mcp_id: UUID,        # MCP ID
      mapping: Mapping | None,  # 名称映射；None → 默认 1:1
      trace_id: str,       # 分布式追踪 ID
  ) -> BindingResult:      # 绑定结果（含 binding_id / state / config_path / pid）
      """执行绑定：冲突检查 → 策略转换 → 写 mcp-config → spawn → 持久化."""
[参数说明]
  参数1: ws_id UUID 必填
  参数2: mcp_id UUID 必填
  参数3: mapping Mapping | None 可选
  参数4: trace_id str 必填
[返回值说明]
  类型: BindingResult
  描述: state=Active 时表示绑定成功
[错误码说明]
  错误码1: BINDING_CONFLICT 409
  错误码2: CONFIG_LOCK_TIMEOUT 503
  错误码3: POOL_FULL 429（透传自 IC-004）
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + API-120]
```

## API-002 unbind（DELETE /bindings/{id}）

```
[接口编号] API-002
[关联契约] IC-022
[实现文件] src/agenthub/application/binding/services.py
[函数签名注释]
  async def unbind(
      binding_id: UUID,    # 绑定 ID
      trace_id: str,
  ) -> None:
      """执行解绑：删 mcp-config → recycle → 标 Released."""
[错误码说明]
  错误码1: BINDING_NOT_FOUND 404
  错误码2: CONFIG_LOCK_TIMEOUT 503
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + API-121]
```

## API-003 list_bindings（GET /bindings）

```
[接口编号] API-003
[关联契约] IC-022
[实现文件] src/agenthub/application/binding/services.py
[函数签名注释]
  async def list_bindings(
      ws_id: UUID,
      page: int,
      size: int,
      trace_id: str,
  ) -> tuple[list[BindingResult], int]:
      """分页查询 workspace 内 binding."""
[来源标注] [DD-M推断:基于 M-B01 list 模式 + MD-MCP#M-B03]
```

## API-004 generate_config（核心底层）

```
[接口编号] API-004
[关联契约] IC-022 + SEC:SEC-011 + ADR-005
[实现文件] src/agenthub/application/binding/generators.py
[函数签名注释]
  async def generate(
      mapping: dict[str, str],
      ws_id: UUID,
      trace_id: str,
  ) -> Path:                # mcp-config 绝对路径
      """L4 单一源写入（temp + atomic rename + 0600 + fcntl SHARED LOCK）."""
[错误码说明]
  错误码1: CONFIG_LOCK_TIMEOUT 503
  错误码2: PATH_TRAVERSAL 400
[性能约束] P95 ≤ 50ms
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + ADR-005]
```

## API-005 revoke_config

```
[接口编号] API-005
[关联契约] IC-022
[实现文件] src/agenthub/application/binding/generators.py
[函数签名注释]
  async def revoke(
      config_path: Path,
      ws_id: UUID,
      trace_id: str,
  ) -> None:
      """原子删除 mcp-config（fcntl EXCLUSIVE LOCK）."""
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + SEC:SEC-011]
```

## API-006 strategy.transform

```
[接口编号] API-006
[关联契约] IC-022
[实现文件] src/agenthub/application/binding/strategies.py
[函数签名注释]
  def transform(
      self,
      mapping: Mapping,
  ) -> Mapping:
      """策略转换（Default → 1:1 + 命名规范化；Custom → 校验 + 规范化）."""
[错误码说明]
  错误码1: PATH_TRAVERSAL 400
  错误码2: MAPPING_TOO_LONG 400
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03 + TD:BR-001~004]
```
