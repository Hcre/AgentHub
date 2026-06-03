# 文件结构合规报告 FC-M-C06-MCP-V1.0-20260603

> 模块: M-C06 SSRF Guard
> 5 项合规检查（soul 4.7）

---

## 1. 合规检查项

| 检查项 | 检查标准 | 实测 | 通过 |
|--------|---------|------|------|
| 目录层级 | 目录层级 ≥ 2 层 | 3 层（ssrf_guard/validators/tests） | ✓ |
| 文件命名 | snake_case | chain.py / blacklist.py / scheme.py / ip_blacklist.py / port.py / redirect.py / dns.py | ✓ |
| 文件职责 | 每个文件职责单一明确 | chain=编排；blacklist=黑名单；5 validator 各 1 文件；tests 测试 | ✓ |
| 依赖关系 | 无循环依赖 | chain → validators/* → blacklist；validators 内无相互调用 | ✓ |
| 最佳实践 | 符合 FastAPI src-layout | 标准 src-layout + 包结构 + __init__.py 完整 | ✓ |

**5/5 全部通过 → 合规度 = 高**

---

## 2. 依赖关系图

```
chain.py
  └─→ validators/base.py
        ├─→ validators/scheme.py
        ├─→ validators/ip_blacklist.py ─→ blacklist.py
        ├─→ validators/port.py
        ├─→ validators/redirect.py (自引用 SSRFChain, max 3 hop)
        └─→ validators/dns.py ─→ [跨模块] M-C04 DNSPinner
```

**无循环依赖 ✓**

---

## 3. 跨模块依赖声明

| 调用方 | 被调方 | 接口 | 处理方式 |
|--------|-------|------|---------|
| validators/dns.py | M-C04 DNSPinner | IC-011 | TYPE_CHECKING 延迟导入；不修改 M-C04 |
| chain.py | M-B05 / M-C02 上游 | IC-007 / IC-009 | 通过调用方处理 SSRFAttempt 上抛 |

**跨模块操作数: 0（D7=100）**

---

## 4. 修复建议

无（5/5 通过）

---

**合规报告结束。**
