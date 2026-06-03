# M-B01 框架决策记录（FDR）

> 框架决策记录 FDR-M-B01-MCP-V1.0-20260602
> 负责模块：M-B01 Market Service
> 来源：[DD-M推断:文件组织关键决策]

---

## FDR-MB01-001 控制器与 FastAPI router 解耦

```
[决策编号] FDR-MB01-001
[决策标题] 控制器类与 router 模块级变量分离
[决策状态] 已接受
[决策内容] MarketController 为类（可被依赖注入装配）；router 为模块级 APIRouter（被 M-A01 include）
[决策理由] 便于在测试中替换 MarketService（依赖注入）；同时保留 FastAPI 标准注册流程
[拒绝的替代方案] 全部用模块级函数（不可注入，单元测试难 mock）
[影响范围] controllers.py 全文
[来源标注] [DD-M推断:CS-MCP#§1.7 测试可替换性]
```

## FDR-MB01-002 缓存代理采用继承而非组合包装

```
[决策编号] FDR-MB01-002
[决策标题] CachedMCPServerRepository 继承 MCPServerRepository
[决策状态] 已接受
[决策内容] 用继承实现装饰器（is-a 关系），保证类型兼容
[决策理由] 1) services 层 type hint 可直接用基类；2) 装饰器意图明确
[拒绝的替代方案] 组合（has-a）：需要外层 wrapper 函数，type hint 复杂
[影响范围] decorators.py / services.py
[来源标注] [DD-001:MD-MCP#M-B01 设计模式 Cache Proxy]
```

## FDR-MB01-003 缓存键命名空间

```
[决策编号] FDR-MB01-003
[决策标题] 缓存 key 命名空间采用 market:server:{id}
[决策状态] 已接受
[决策内容] market:server:{uuid} 用于详情；market:server:__null__ 用于墓碑
[决策理由] 与 M-D03 DS-020 Redis 键命名约定一致（{module}:{resource}:{id}）
[拒绝的替代方案] 散列命名（无前缀）：多模块共享 Redis cluster 时易冲突
[影响范围] decorators.py
[来源标注] [DD-M推断:DS-020~026 键命名规范]
```

## FDR-MB01-004 测试 20 用例分组

```
[决策编号] FDR-MB01-004
[决策标题] 测试分 6 组覆盖 20 用例
[决策状态] 已接受
[决策内容] TestMarketServiceList / TestMarketServiceGetDetail / TestMarketServiceSearch / TestCacheProxy / TestRepositoryEdge / TestConcurrencyAndController
[决策理由] 按业务功能（list/get/search/cache/edge/controller）分组，便于失败定位
[拒绝的替代方案] 单一 TestMarketService 类：函数膨胀，违反 [CS-001 §1.7] 命名规范
[影响范围] tests/test_market.py
[来源标注] [DD-001:MD-MCP#M-B01 用例数 20]
```

## FDR-MB01-005 跨模块依赖通过 TYPE_CHECKING

```
[决策编号] FDR-MB01-005
[决策标题] 跨模块 ORM/Client 引用全部走 TYPE_CHECKING
[决策状态] 已接受
[决策内容] repositories.py 与 decorators.py 对 M-D01 / M-D03 的引用使用 `if TYPE_CHECKING`
[决策理由] 1) 避免运行时循环导入；2) 编译期类型仍可解析（mypy 满意）
[拒绝的替代方案] 直接顶层 import：M-D01 导入 M-B01 装饰器时会发生循环
[影响范围] repositories.py / decorators.py
[来源标注] [DD-001:CS-MCP#§1.5 导入规范]
```

## FDR-MB01-006 DTO 全部 frozen + extra="forbid"

```
[决策编号] FDR-MB01-006
[决策标题] 所有 Pydantic DTO 设置 frozen=True, extra="forbid"|"ignore"
[决策状态] 已接受
[决策内容] 请求体 extra="forbid"（拒绝未知字段），响应体 extra="ignore"（向后兼容）
[决策理由] 1) 防止业务侧意外修改；2) 严格校验入参；3) 兼容旧字段
[拒绝的替代方案] 全部 ignore：入参也允许未知字段可能引入 bug
[影响范围] schemas.py
[来源标注] [DD-M推断:API 严格性 + [CS-001 §1.3]]
```

## FDR-MB01-007 错误码统一前缀 MARKET_*

```
[决策编号] FDR-MB01-007
[决策标题] M-B01 错误码统一以 MARKET_ 前缀
[决策状态] 已接受
[决策内容] MARKET_NOT_FOUND / MARKET_DB_UNAVAILABLE / MARKET_VALIDATION / MARKET_INTERNAL
[决策理由] 1) 客户端可基于前缀路由；2) 与 IC-001 统一响应包装层一致
[拒绝的替代方案] 沿用通用 NOT_FOUND / DB_ERROR：跨模块无差异化
[影响范围] controllers.py（HTTPException detail）
[来源标注] [DD-001:IC-MCP#API-100 + IC-MCP#IC-001 错误码规范]
```
