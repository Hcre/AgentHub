# 框架决策记录 FDR-M-C06-MCP-V1.0-20260603

> 模块: M-C06 SSRF Guard

---

## FDR-001 采用 Chain of Responsibility 模式

```
[决策编号]   FDR-001
[决策标题]   5 层 SSRF 校验采用 Chain of Responsibility
[决策状态]   已接受
[决策内容]   顺序装配 Scheme→IPBlacklist→Port→Redirect→DNS 5 validator
[决策理由]   [DD-001:MD-M-C06] 明确指定 Chain of Responsibility；5 层短路清晰；任一层可独立测试
[拒绝的替代方案]
  方案B: 单一函数内 5 段 if-else — 违反 R10 单文件 ≤ 20 函数；难单元测试
  方案C: 规则引擎（Drools 等）— 过度设计，5 条规则用链足够
[影响范围]   chain.py + validators/* 7 个文件
[相关FDR]    FDR-002, FDR-003
[来源标注]   [DD-001:MD-M-C06 + FS-015]
```

---

## FDR-002 validators/ 子包拆分

```
[决策编号]   FDR-002
[决策标题]   5 validator 拆分为独立子包
[决策状态]   已接受
[决策内容]   validators/ 子包下 6 文件（base + 5 具体）
[决策理由]   灵魂4.11对比方案A（8.94）vs方案B（6.61），差值23≥5；避免单文件函数数超限
[拒绝的替代方案]
  方案B: 全部塞入 chain.py — 单文件 25+ 函数违反 4.2 ≤ 20 上限
[影响范围]   validators/ 子包
[相关FDR]    FDR-001
[来源标注]   [DD-M推断:soul 4.2/4.11 客观对比]
```

---

## FDR-003 fail-secure 默认拒绝

```
[决策编号]   FDR-003
[决策标题]   DNS 解析失败 → 默认拒绝
[决策状态]   已接受
[决策内容]   DNSValidator 在 resolve 失败时返回 block（不通过）
[决策理由]   [DD-001:EX-004] 明确 fail-secure；防攻击者利用 DNS 故障绕过
[拒绝的替代方案]
  方案B: 失败放行 — 极高安全风险，违反 ADR-004
[影响范围]   validators/dns.py
[相关FDR]    FDR-001
[来源标注]   [DD-001:EX-004 + ADR-004 + SEC:SEC-004]
```

---

## FDR-004 黑名单懒加载

```
[决策编号]   FDR-004
[决策标题]   IPBlacklist 在首次 check 触发时加载
[决策状态]   已接受
[决策内容]   __init__ 不触发 I/O；首次 check() 内部加载
[决策理由]   启动时延优化；支持热更新（reload_from_vault）
[拒绝的替代方案]
  方案B: __init__ 即加载 — 增加模块导入时延；难以热更新
[影响范围]   blacklist.py, chain.py
[相关FDR]    -
[来源标注]   [DD-M推断:启动性能优化 + 热更新需求]
```

---

## FDR-005 跨模块依赖通过 TYPE_CHECKING

```
[决策编号]   FDR-005
[决策标题]   M-C06 → M-C04 DNSValidator 跨模块引用采用 TYPE_CHECKING
[决策状态]   已接受
[决策内容]   validators/dns.py 中 `if TYPE_CHECKING: from agenthub.infrastructure.dns_pinning.pinner import DNSPinner`
[决策理由]   避免循环导入；D7=100 硬约束（不修改 M-C04 文件）；运行时通过 DI 注入
[拒绝的替代方案]
  方案B: 运行时直接 import — 触发 D7 违规警告
[影响范围]   validators/dns.py
[相关FDR]    -
[来源标注]   [DD-M推断:soul 多实例隔离协议 + D7 硬约束]
```

---

**框架决策记录结束（5 条）**
