# 文件框架结构 FF-M-C04-MCP-V1.0-20260603

> 模块：M-C04 DNS Pinning
> 编制：DD-M-C04
> 来源：[DD-001:FS-013 + MD-MCP: M-C04] + [DD-M推断:扩展子模块映射]

---

## 一、模块基本信息

| 项 | 值 |
|----|-----|
| 模块编号 | M-C04 |
| 模块名称 | DNS Pinning（DNS 钉扎） |
| 关联技术选型 | TS-018 yarl / TS-019 aiodns / TS-012 Redis 7.2 cluster |
| 设计模式 | Cache Proxy + Singleton（yarl 单对象 + Redis 缓存代理） |
| 关联接口契约 | IC-011（DNS.resolve） |
| 关联设计规范 | FS-013 / MD-MCP:M-C04 / CS-MCP §1 / IC-MCP:IC-011 / TD-MCP:RSK-04, S-032 |
| 上游依赖模块 | M-C06（SSRF Guard，黑名单数据源）+ M-D03（Cache & Queue，Redis 客户端注入） |
| 下游被依赖模块 | M-B05（MCP Create，调用 resolve）/ M-C01（Sandbox，可选调用） |
| 测试用例数 | 20（MD 规范） |

---

## 二、文件目录结构

```
[模块根] src/agenthub/infrastructure/dns_pinning/
├── __init__.py              ← [职责：模块初始化，导出公共接口 DNSPinner/PinCache/异常类]
├── pinner.py                ← [职责：DNSPinner Singleton 主入口，编排 resolver/cache/blacklist/redirect；对应 MD 子模块 pinning/]
├── cache.py                 ← [职责：PinCache Redis Cache Proxy（TTL 60s）；对应 MD 子模块 cache/]
├── resolver.py              ← [职责：AsyncResolver aiodns 异步 DNS 解析封装；对应 MD 子模块 resolver/]
├── blacklist.py             ← [职责：IPBlacklist 黑名单 CIDR 匹配（与 M-C06 共享配置）；支撑 BlacklistIPError 异常触发]
├── redirect.py              ← [职责：RedirectChecker 重定向重校验（max 3 跳循环防护）；对应 MD 子模块 redirect/]
├── exceptions.py            ← [职责：DNS 领域异常定义（DNSResolveError / BlacklistIPError / RedirectLoopError）]
└── tests/
    ├── __init__.py          ← [职责：测试包初始化，pytest 探针]
    ├── test_pinner.py       ← [职责：DNSPinner 端到端测试，含 4 个子模块协作场景]
    ├── test_cache.py        ← [职责：PinCache Redis 缓存测试，含 hit/miss/TTL 过期]
    ├── test_resolver.py     ← [职责：AsyncResolver aiodns 异步解析测试，含 IPv4/IPv6/AAAA]
    ├── test_blacklist.py    ← [职责：IPBlacklist CIDR 匹配测试，含 IPv4/IPv6 段]
    └── test_redirect.py     ← [职责：RedirectChecker 重定向重校验测试，含循环防护/max 3 跳]
```

[DD-M洞察-3] 相对 FS-013 官方 2 文件结构，本框架在 MD-004 4 子模块驱动下扩展为 7 源文件 + 5 测试文件，文件数 12 在 soul 4.2 约束 `[模块复杂度×2, 模块复杂度×5]` = `[6, 15]` 范围内，结构合理性可证。

---

## 三、文件间依赖关系

```
__init__.py → pinner.py
            → cache.py
            → exceptions.py

pinner.py → cache.py          （依赖 PinCache 做 Redis 缓存读写）
         → resolver.py        （依赖 AsyncResolver 做 aiodns 异步解析）
         → blacklist.py       （依赖 IPBlacklist 做 IP 黑名单匹配）
         → redirect.py        （依赖 RedirectChecker 做重定向重校验）
         → exceptions.py      （抛出 DNSResolveError/BlacklistIPError/RedirectLoopError）

cache.py → exceptions.py      （抛出 CacheBackendError）
resolver.py → exceptions.py   （抛出 DNSResolveError）

tests/* → src/agenthub/infrastructure/dns_pinning/*   （被测对象）

跨模块依赖（不可直接依赖其他模块代码，必须通过依赖注入或 shared config 共享）：
  pinner.py → agenthub.infrastructure.ssrf_guard.blacklist    [DD-M推断:与 M-C06 共享 CIDR 配置]
  cache.py  → agenthub.data.cache.client.RedisClusterClient  [DD-M推断:复用 M-D03 Redis 客户端单例]
```

[DD-M洞察-4] 上述依赖图无环（pinner 是唯一汇聚点，cache/resolver/blacklist/redirect 均为叶子），满足 soul 4.7 检查项 4「无循环依赖」。

---

## 四、文件职责清单

| 文件路径 | 职责 | 关联类/函数 | 状态机 | 异常抛出 |
|---------|------|-----------|--------|---------|
| `__init__.py` | 模块公共接口导出 | DNSPinner / PinCache / DNSResolveError / BlacklistIPError / RedirectLoopError | 无 | 无 |
| `pinner.py` | Singleton 主入口，编排 4 子模块 | class DNSPinner, async resolve(), async recheck_redirect(), async warmup(), async aclose() | Singleton 生命周期 | DNSResolveError, BlacklistIPError, RedirectLoopError |
| `cache.py` | Redis Cache Proxy | class PinCache, async get(), async set(), async delete(), async ttl() | 无 | CacheBackendError |
| `resolver.py` | aiodns 异步 DNS 解析 | class AsyncResolver, async resolve_hostname() | 无 | DNSResolveError |
| `blacklist.py` | IP 黑名单 CIDR 匹配 | class IPBlacklist, def is_blacklisted(), def add_cidr() | 加载中 → 已加载 | 无 |
| `redirect.py` | 重定向重校验（循环防护） | class RedirectChecker, async check(), def _hop_count() | 0 跳 → 1 跳 → ... → 3 跳 | RedirectLoopError |
| `exceptions.py` | DNS 领域异常基类 | class DNSResolveError, class BlacklistIPError, class RedirectLoopError, class CacheBackendError | 无 | 无 |
| `tests/__init__.py` | pytest 测试包初始化 | 无 | 无 | 无 |
| `tests/test_pinner.py` | DNSPinner 端到端测试 | test_resolve_xxx, test_redirect_xxx | 无 | 无 |
| `tests/test_cache.py` | PinCache 缓存测试 | test_get_set, test_ttl, test_miss | 无 | 无 |
| `tests/test_resolver.py` | AsyncResolver 解析测试 | test_resolve_ipv4, test_resolve_ipv6, test_failure | 无 | 无 |
| `tests/test_blacklist.py` | IPBlacklist 匹配测试 | test_ipv4_match, test_ipv6_match, test_not_in_list | 无 | 无 |
| `tests/test_redirect.py` | RedirectChecker 重定向测试 | test_check_allow, test_check_loop, test_check_max_hops | 无 | 无 |

---

## 五、模块边界守护

```
本DD-M负责: M-C04
操作文件数: 12（仅 M-C04 目录下）
跨模块文件数: 0
状态: 合规 (D7 = 100)
```

跨模块代码仅通过以下方式接触：
1. **配置共享**（黑名单 CIDR 列表通过 Settings/config 注入，不直接 import 其他模块代码）
2. **客户端注入**（Redis 客户端通过工厂方法或 DI 容器注入，pinner.py 不直接 `from agenthub.data.cache...`）
3. **接口契约**（通过 IC-011 调用本模块，本模块不调用其他模块，仅暴露能力）

---

## 六、来源标注

| 决策点 | 来源 |
|--------|------|
| 7 文件结构（vs FS-013 原始 2 文件） | [DD-M推断:依据 MD-004 4 子模块拆分+异常独立维护] |
| cache.py 独立拆分 | [DD-001:FS-013] |
| exceptions.py 新增 | [DD-M推断:依据 MD-004 异常处理段 3 类异常] |
| blacklist.py 拆分 | [DD-M推断:依据 MD-004 异常处理 BlacklistIPError 触发点需独立 IP 匹配能力] |
| resolver.py 拆分 | [DD-M推断:依据 MD-004 子模块 resolver/ 职责独立] |
| redirect.py 拆分 | [DD-M推断:依据 MD-004 子模块 redirect/ + 重定向 max 3 跳约束] |
| 跨模块黑名单共享 | [DD-M推断:依据 M-C06 FS-015 已有 blacklist.py + SSRF 防御同样需要黑名单] |
| 测试文件 5 份拆分 | [DD-M推断:依据 5 个核心源文件一一对应，单文件不超过 20 函数约束] |

---

**[DD-M洞察-5]** M-C04 的核心价值是「防 DNS 重绑定攻击」(DNS Rebinding)：通过 yarl URL 单对象 Pin 第一次解析的 IP 持久化到 Redis 60s 内，阻断攻击者通过 DNS 切换绕过 SSRF Guard（[TD:RSK-04]）。此安全性价值高于性能价值，注释必须明确 Pin 的「持久化 + 短 TTL」组合防御原理。

**文件框架结构文档结束。**
