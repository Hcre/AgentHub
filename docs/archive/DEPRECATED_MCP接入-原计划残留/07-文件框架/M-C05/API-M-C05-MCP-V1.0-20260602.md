# 接口注释清单 API-M-C05-MCP-V1.0-20260602

## IC-012 acl.apply（API-240）

```
[接口编号] IC-012
[关联契约] IC-012（来自DD-001）
[实现文件] src/agenthub/infrastructure/network_acl/controller.py
[函数签名注释]
  async def apply(
      workspace_id: uuid.UUID,  # 必填 工作区 ID
      rules: list[ACLRule]       # 必填 待应用规则（非空）
  ) -> list[uuid.UUID]:         # 已应用规则 ID 列表
      """
      应用 ACL 规则到指定 workspace

      Args:
          workspace_id: 工作区 ID
          rules: 待应用规则

      Returns:
          成功应用的规则 ID 列表（空 = 全部幂等跳过）

      Raises:
          ACLBackendUnavailable: 后端不可用 (503 ACL_BACKEND_UNAVAILABLE)
          ACLConflict: 规则冲突 (409 ACL_CONFLICT)

      Example:
          >>> await controller.apply(ws_id, [rule1, rule2])
          [UUID('...'), UUID('...')]
      """
[错误码]
  ACL_BACKEND_UNAVAILABLE 503 - 切换备选 backend
  ACL_CONFLICT 409 - 规则冲突
[并发安全] per-workspace 串行（PG row-lock）
[幂等性] 是 / 幂等键: rule_hash
[性能约束] P95 ≤ 1s
[来源标注] [DD-001:IC-012]
```

## API-C05-INTERNAL revoke（IC-012 子操作）

```
[函数签名注释]
  async def revoke(
      rule_id: uuid.UUID  # 必填 规则 ID
  ) -> None:
      """
      撤销单条 ACL 规则

      Raises:
          NotFoundError: 规则不存在 (404)
      """
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
```

## API-C05-BACKEND.*（三 backend 统一接口）

```
[函数签名注释]
  async def apply(
      rules: list[ACLRule]  # 必填
  ) -> list[uuid.UUID]:

  async def revoke(
      rule_id: uuid.UUID  # 必填
  ) -> None:

  async def healthcheck() -> bool:  # True=健康
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
[实现]
  - IptablesBackend: iptables 子进程封装
  - DockerNetworkBackend: aiodocker 客户端
  - IpsetBackend: ipset -A/-D 封装
```

**接口注释覆盖率: 100%（1 IC + 2 internal API = 3/3）**
