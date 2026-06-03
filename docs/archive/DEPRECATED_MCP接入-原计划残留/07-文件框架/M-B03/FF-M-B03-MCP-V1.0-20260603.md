# 文件框架结构 FF-M-B03-MCP-V1.0-20260603

> M-B03 Binding Engine 文件框架，遵循 FS-007 + DD-001 详细设计
> 来源标注 100%，模块边界严格隔离

---

## [模块编号] M-B03
## [模块名称] Binding Engine
## [文件框架]

```
src/agenthub/application/binding/
├── __init__.py                ← [职责：模块入口，导出公共符号]
│   - 导出 BindingController / BindingService / BindingStrategy / ConfigGenerator
│   - 暴露 DTO: BindForm / BindingResult / Mapping
│   - 暴露异常: BindingConflictError / ConfigLockTimeoutError / PathTraversalError / MappingValidationError
├── controllers.py             ← [职责：FastAPI 路由层，承接 M-A01 转发]
│   - 类 BindingController
│     - bind(form) -> BindingResult   [POST /bindings]
│     - unbind(binding_id) -> None    [DELETE /bindings/{id}]
│     - list_bindings(ws_id, page, size) -> BindingListResponse [GET /bindings]
│   - 工厂函数 build_controller(service)
├── services.py                ← [职责：业务编排]
│   - 类 BindingService
│     - bind(ws_id, mcp_id, mapping, trace_id) -> BindingResult
│     - unbind(binding_id, trace_id) -> None
│     - list_bindings(ws_id, page, size, trace_id) -> tuple[list, int]
│     - select_strategy(mapping_kind) -> BindingStrategy
├── strategies.py              ← [职责：Strategy 模式实现]
│   - 类 BindingStrategy (ABC)
│     - transform(mapping) -> Mapping [abstract]
│     - default_mapping() -> Mapping [abstract]
│   - 类 DefaultMappingStrategy（1:1 + M-C08 命名规范化）
│   - 类 CustomMappingStrategy（自定义 + 路径遍历检测）
├── generators.py              ← [职责：mcp-config L4 单一源（ADR-005）]
│   - 类 ConfigGenerator
│     - generate(mapping, ws_id, trace_id) -> Path
│     - revoke(config_path, ws_id, trace_id) -> None
│     - resolve_path(ws_id, mcp_id) -> Path
├── exceptions.py              ← [职责：领域异常定义]
│   - BindingConflictError (409)
│   - ConfigLockTimeoutError (503)
│   - PathTraversalError (400)
│   - MappingValidationError (422)
├── schemas.py                 ← [职责：Pydantic DTO]
│   - BindForm (frozen)
│   - BindingResult (frozen)
│   - Mapping = dict[str, str]
├── repository.py              ← [职责：BindingRepository ABC]
│   - exists(ws_id, mcp_id) -> bool
│   - add(...) -> UUID
│   - get(binding_id) -> BindingResult | None
│   - list(ws_id, page, size, trace_id) -> tuple[list, int]
│   - mark_released(binding_id, trace_id) -> None
└── tests/                     ← [职责：单元测试]
    ├── __init__.py
    ├── test_controllers.py    ← 6 个测试场景
    ├── test_services.py       ← 7 个测试场景
    ├── test_strategies.py     ← 7 个测试场景
    └── test_generators.py     ← 5 个测试场景
```

## [文件间依赖关系]

```
controllers.py → services.py → strategies.py
                              → generators.py
                              → repository.py
                              → schemas.py
                              → exceptions.py
tests/ → [被测试文件]
```

[依赖约束]
- controllers → services（严格三层架构）
- services → strategies / generators / repository
- repository → schemas（仅类型）
- strategies → exceptions / M-C08 transformer
- generators → exceptions

## [模块边界]

- 唯一模块：M-B03
- 跨模块依赖：M-B02（pool.spawn via IC-004）、M-C08（NameTransformer）、M-D01（Repository 实现）
- 跨模块调用方式：全部 in-proc（IC-022），禁止远程 RPC
- 跨模块文件操作数：0（已严格隔离）

## [来源标注]

[DD-001:FS-007 + MD-MCP-V1.0-20260602#M-B03 + IC-004 + SEC:SEC-011 + ADR-005]

[DD-M洞察]
- 1. ConfigGenerator 必须是 L4 单一源（ADR-005），禁止其他模块直接 open() mcp-config
- 2. fcntl.flock 与 fcntl.fcntl 不同，Linux 兼容需用 flock（POSIX）
- 3. M-B03 与 M-B02 解耦通过 in-proc 接口（IC-004），未来若 M-B02 远程化需重新设计

## [阶梯退出检查]

① 目录层级 ≥2：是（4 层） ② 文件命名合规：是（snake_case + M-B03 模块前缀通过目录隔离） ③ 职责定义：是 ④ 依赖关系明确：是 ⑤ 最佳实践：是（FastAPI 推荐布局）
