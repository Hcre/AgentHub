# 接口注释清单 API-M-C06-MCP-V1.0-20260603

> 模块: M-C06 SSRF Guard
> 关联 IC: IC-013 (ssrf.check), IC-011 (dns.resolve, 跨模块)
> 输出供 DD-S 阶段在代码骨架中按本清单实现函数签名

---

## API-MC06-001 ssrf.check（IC-013）

```
[接口编号]   API-MC06-001
[关联契约]   IC-013 ssrf.check
[实现文件]   src/agenthub/infrastructure/ssrf_guard/chain.py
[函数签名注释]
  class SSRFChain:
      def check(self, url: yarl.URL) -> CheckResult:
          """
          SSRF 校验主入口（IC-013）

          Args:
              url: 待校验 URL（已通过 yarl 解析）

          Returns:
              CheckResult(pass=bool, reason=str, layer=str)

          Raises:
              SSRFAttempt: 拒绝时（调用方处理，[DD-001:EX-004]）
              SSRFCheckError: 校验器自身异常

          Example:
              >>> chain = SSRFChain.build_default_chain()
              >>> chain.check(URL("https://example.com"))
              CheckResult(pass_=True, reason="", layer="")
          """
[参数说明]
  url: yarl.URL 必填 任意 yarl 解析后的 URL
[返回值说明]
  pass_: bool True 通过 / False 拒绝
  reason: str 拒绝原因（pass=True 时为空）
  layer: str 拒绝层（scheme/ip_blacklist/port/redirect/dns）
[错误码说明]
  SSRFAttempt: 拒绝时由调用方处理
  SSRFCheckError: 校验器内部异常（fail-secure 默认 block）
[性能约束] P95 < 50ms
[并发安全] 线程安全
[幂等性] 是（url → result；黑名单版本周期内）
[来源标注] [DD-001:IC-013 + MD-M-C06 + EX-004]
```

---

## API-MC06-002 check_default_chain（构造）

```
[接口编号]   API-MC06-002
[关联契约]   IC-013（工厂方法）
[实现文件]   src/agenthub/infrastructure/ssrf_guard/chain.py
[函数签名注释]
  @classmethod
  def build_default_chain(cls) -> "SSRFChain":
      """
      装配 5 validator 默认链（IC-013 工厂）

      Returns:
          装配好的 SSRFChain 实例（Scheme→IPBlacklist→Port→Redirect→DNS）
      """
[参数说明] 无
[返回值说明] SSRFChain 实例
[错误码说明] 无
[性能约束] 启动一次性开销，< 10ms
[并发安全] 是
[来源标注] [DD-001:MD-M-C06 + FS-015]
```

---

## 跨模块引用: IC-011 dns.resolve

```
[接口编号]   API-MC06-003 (跨模块引用)
[关联契约]   IC-011 dns.resolve（来自 M-C04）
[调用位置]   src/agenthub/infrastructure/ssrf_guard/validators/dns.py: DNSValidator._do_validate
[调用方式]   self._pinner.resolve(url) -> str (pinned_ip)
[依赖模块]   M-C04 DNS Pinning（不修改 M-C04 任何文件，D7=100）
[来源标注] [DD-001:IC-011 + MD-M-C06]
```

---

## 接口覆盖统计

| 接口契约 | 实现位置 | 状态 |
|---------|---------|------|
| IC-013 | chain.py::SSRFChain.check | 已注释 |
| IC-011 | validators/dns.py::DNSValidator | 已注释（跨模块） |

**接口注释覆盖率: 100%**
