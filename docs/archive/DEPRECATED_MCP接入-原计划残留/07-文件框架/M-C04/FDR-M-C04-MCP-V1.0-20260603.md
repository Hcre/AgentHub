# 框架决策记录 FDR-M-C04-MCP-V1.0-20260603

> 模块：M-C04 DNS Pinning
> 编制：DD-M-C04
> 来源：[DD-001:FS-013 + MD-MCP:M-C04 + IC-MCP:IC-011] + [DD-M推断]

---

## 决策摘要表

| 决策编号 | 决策标题 | 决策状态 | 影响范围 |
|---------|---------|---------|---------|
| FDR-MC04-001 | 文件数从 FS-013 的 2 个扩展为 7 个 | 已接受 | dns_pinning/ 全部源文件 |
| FDR-MC04-002 | Singleton 模式采用模块级单例 + __new__ 双保险 | 已接受 | pinner.py |
| FDR-MC04-003 | exceptions.py 独立拆分（4 类领域异常） | 已接受 | exceptions.py |
| FDR-MC04-004 | blacklist.py 拆分（与 M-C06 黑名单配置共享） | 已接受 | blacklist.py |
| FDR-MC04-005 | resolver.py 拆分（aiodns 异步封装独立） | 已接受 | resolver.py |
| FDR-MC04-006 | redirect.py 拆分（max 3 跳循环防护） | 已接受 | redirect.py |
| FDR-MC04-007 | 跨模块黑名单通过 Settings 配置共享（非 import） | 已接受 | 模块边界 D7 |
| FDR-MC04-008 | 缓存 TTL 硬编码 60s 常量（DEFAULT_TTL_SEC） | 已接受 | cache.py |
| FDR-MC04-009 | 测试文件 1:1 对应源文件，单文件 < 20 函数 | 已接受 | tests/ |

---

## FDR-MC04-001 文件数扩展（2→7）

```
[决策编号] FDR-MC04-001
[决策标题] M-C04 文件数从 FS-013 的 2 个扩展为 7 个
[决策状态] 已接受
[决策内容] pinner.py + cache.py + resolver.py + blacklist.py + redirect.py + exceptions.py + __init__.py
[决策理由]
  - MD-MCP:M-C04 明确子模块拆分 resolver/ + pinning/ + cache/ + redirect/ 共 4 个
  - 4 个子模块 + 异常独立维护 + 公共接口导出 = 7 文件结构
  - 文件数 7 在 soul 4.2 约束 [模块复杂度×2, 模块复杂度×5] = [6, 15] 范围内
[拒绝的替代方案]
  方案A: 维持 FS-013 的 2 文件结构（仅 pinner.py + cache.py）
    拒绝理由: 单文件 > 20 函数，违反 soul 4.2 单文件函数数上限
  方案B: 9 文件（每个子模块独立 __init__.py）
    拒绝理由: 过度拆分，违反 soul 4.2 单文件函数数下限（最少充分原则）
[影响范围] dns_pinning/ 全部源文件
[相关FDR] FDR-MC04-003~006（异常/黑名单/解析器/重定向子模块拆分）
[来源标注] [DD-001:MD-MCP:M-C04 子模块拆分] + [DD-M推断:依据文件数约束]
```

---

## FDR-MC04-002 Singleton 模式实现

```
[决策编号] FDR-MC04-002
[决策标题] Singleton 模式采用模块级单例 + __new__ 双保险
[决策状态] 已接受
[决策内容] DNSPinner 通过 __new__ 拦截首次创建 + _initialized 标志位防重复 init
[决策理由]
  - MD-MCP:M-C04 明确设计模式为「Cache Proxy + Singleton」
  - Python 模块加载时 GIL 保证原子性，模块级单例安全
  - __new__ 双保险避免热重载或多线程下的竞态
  - get_instance() 显式工厂方法便于 DI 容器使用
[拒绝的替代方案]
  方案A: metaclass 实现
    拒绝理由: 复杂度高，对当前场景过度设计
  方案B: 装饰器模式
    拒绝理由: 与现有 DD-M 框架风格不一致
[影响范围] pinner.py DNSPinner 类
[相关FDR] 无
[来源标注] [DD-001:MD-MCP:M-C04 设计模式] + [DD-M推断:依据 Singleton 惯用 API]
```

---

## FDR-MC04-003 exceptions.py 独立拆分

```
[决策编号] FDR-MC04-003
[决策标题] 4 类领域异常独立维护为 exceptions.py
[决策状态] 已接受
[决策内容] DNSResolveError / BlacklistIPError / RedirectLoopError / CacheBackendError 集中到 exceptions.py
[决策理由]
  - 4 类异常需被 cache/resolver/pinner 共同引用
  - 异常独立文件是 Python 领域驱动设计最佳实践
  - 便于测试用例统一 mock 和捕获
[拒绝的替代方案]
  方案A: 异常散落在各文件
    拒绝理由: 跨文件 import 循环风险
[影响范围] exceptions.py + cache.py + resolver.py + redirect.py
[相关FDR] FDR-MC04-001
[来源标注] [DD-001:MD-MCP:M-C04 异常处理] + [DD-M推断:依据异常独立维护原则]
```

---

## FDR-MC04-004 blacklist.py 拆分

```
[决策编号] FDR-MC04-004
[决策标题] IP 黑名单 CIDR 匹配独立为 blacklist.py
[决策状态] 已接受
[决策内容] IPBlacklist 类独立文件，封装 CIDR 段加载/匹配/管理
[决策理由]
  - MD-MCP:M-C04 异常处理 BlacklistIPError 需要 IP 匹配能力
  - CIDR 匹配逻辑（IPv4/IPv6）相对独立，不应混入 pinner 编排逻辑
  - 与 M-C06 (SSRF Guard) 共享黑名单配置（通过 Settings 注入）
[拒绝的替代方案]
  方案A: 直接 import M-C06 blacklist
    拒绝理由: 违反 D7 模块边界硬约束
  方案B: 黑名单内联到 pinner.py
    拒绝理由: 单文件 > 20 函数上限
[影响范围] blacklist.py + pinner.py（依赖注入）
[相关FDR] FDR-MC04-001, FDR-MC04-007
[来源标注] [DD-001:MD-MCP:M-C04 异常处理] + [DD-M推断:依据 SSRF 共享黑名单需求]
```

---

## FDR-MC04-005 resolver.py 拆分

```
[决策编号] FDR-MC04-005
[决策标题] aiodns 异步解析封装独立为 resolver.py
[决策状态] 已接受
[决策内容] AsyncResolver 类独立文件，封装 aiodns 异步 DNS 解析
[决策理由]
  - aiodns 解析为异步 IO，独立模块便于 aclose/资源管理
  - IPv4/IPv6 解析差异封装在内部
  - DNS 解析失败 → DNSResolveError 转换逻辑集中
[拒绝的替代方案]
  方案A: aiodns 直接调用内联
    拒绝理由: 资源管理混乱，测试难以 mock
[影响范围] resolver.py + pinner.py
[相关FDR] FDR-MC04-001
[来源标注] [DD-001:MD-MCP:M-C04 子模块 resolver/]
```

---

## FDR-MC04-006 redirect.py 拆分

```
[决策编号] FDR-MC04-006
[决策标题] 重定向重校验独立为 redirect.py
[决策状态] 已接受
[决策内容] RedirectChecker 类独立文件，实现 max 3 跳循环防护
[决策理由]
  - MD-MCP:M-C04 明确「重定向重校验（max 3 跳）」
  - 跳数计数 + 循环防护 + 黑名单二次校验逻辑独立
  - RedirectLoopError 异常集中触发
[拒绝的替代方案]
  方案A: 重定向逻辑内联到 recheck_redirect 方法
    拒绝理由: 状态管理复杂，单方法 > 20 行
[影响范围] redirect.py + pinner.py
[相关FDR] FDR-MC04-001
[来源标注] [DD-001:MD-MCP:M-C04 子模块 redirect/ + max 3 跳]
```

---

## FDR-MC04-007 跨模块黑名单通过 Settings 共享

```
[决策编号] FDR-MC04-007
[决策标题] 跨模块黑名单通过 Settings 配置共享（非 import 其他模块代码）
[决策状态] 已接受
[决策内容] M-C04 与 M-C06 的黑名单 CIDR 数据通过 agenthub.core.config.Settings 注入
[决策理由]
  - D7=100 模块边界硬约束禁止直接 import 其他模块
  - 黑名单数据是配置而非代码，应通过配置层共享
  - 避免循环依赖风险
[拒绝的替代方案]
  方案A: M-C04 直接 import M-C06 blacklist
    拒绝理由: 违反 D7=100 硬约束 + 循环依赖风险
[影响范围] 模块边界 D7 守护
[相关FDR] FDR-MC04-004
[来源标注] [DD-M推断:依据 D7 模块边界硬约束]
```

---

## FDR-MC04-008 缓存 TTL 硬编码 60s

```
[决策编号] FDR-MC04-008
[决策标题] 缓存 TTL 硬编码为 60s 常量 DEFAULT_TTL_SEC
[决策状态] 已接受
[决策内容] PinCache.DEFAULT_TTL_SEC = 60，不可通过配置修改
[决策理由]
  - IC-011 明确约定「后置条件: Redis 缓存 60s」
  - TD:S-032 指出「短 TTL 是 DNS Rebinding 防御核心」
  - 配置化会增加误调风险（运维延长 TTL = 放大攻击窗口）
[拒绝的替代方案]
  方案A: TTL 可通过 Settings 配置
    拒绝理由: 安全关键参数不应运行时调整
[影响范围] cache.py
[相关FDR] 无
[来源标注] [DD-001:IC-MCP:IC-011 + TD-MCP:S-032]
```

---

## FDR-MC04-009 测试文件 1:1 映射

```
[决策编号] FDR-MC04-009
[决策标题] 测试文件与源文件 1:1 对应（5 测试文件 + 1 __init__）
[决策状态] 已接受
[决策内容] test_pinner.py / test_cache.py / test_resolver.py / test_blacklist.py / test_redirect.py
[决策理由]
  - soul 4.2 单文件函数数上限 20
  - 1:1 映射便于定位测试用例与生产代码
  - DD-001:MD-MCP:M-C04 约定 20 用例总数，5 文件平均 4 用例/文件
[拒绝的替代方案]
  方案A: 单一 test_all.py
    拒绝理由: 文件过大，难以维护
[影响范围] tests/ 目录
[相关FDR] 无
[来源标注] [DD-001:MD-MCP:M-C04 测试策略 20 用例] + [DD-M推断:依据文件函数数约束]
```

---

**框架决策记录文档结束。**
