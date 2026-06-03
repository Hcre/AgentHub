# M-C07 Secret Manager 框架决策记录 FDR-M-C07-MCP-V1.0-20260602

> [模块编号] M-C07  [关联规范] soul §4.13 + §4.11

---

## FDR-M-C07-001  采用 Proxy + Cache Proxy 双层模式

```
[决策编号] FDR-M-C07-001
[决策标题] VaultClient 采用 Proxy + Cache Proxy 双层模式
[决策状态] 已接受
[决策内容]
  VaultClient 作为统一入口（Proxy），内部组合 TokenManager / Transit / SecretCache 三个协作者；
  SecretCache 仅作用于 get 路径的 30s 短期 token 缓存，密文与 decrypt 明文一律不入缓存。
[决策理由]
  - DD-001 模块细化方案 MD-M-C07 明确指定 Proxy + Cache Proxy
  - TDR-010 要求 secret 短期缓存以降低 Vault QPS
  - 30s TTL 兼顾一致性与性能；超过 30s 则 token 旋转亦可自然失效
[拒绝的替代方案]
  方案A: 单纯 Proxy（无缓存） — 拒绝理由：无法吸收 100QPS 突发流量，Vault 易触发 429
  方案B: 跨进程 Redis 缓存 — 拒绝理由：增加 M-D03 耦合；secret 缓存属于进程内短期一致性，跨进程反而引入失效复杂度
[影响范围] vault_client.py / cache.py / 全模块 7 个 API
[相关FDR] FDR-M-C07-002
[来源标注] [DD-001:MD-M-C07 + TDR-010]
```

## FDR-M-C07-002  SecretCache 仅缓存 KV v2 读取路径

```
[决策编号] FDR-M-C07-002
[决策标题] SecretCache 不缓存 Transit 解密明文
[决策状态] 已接受
[决策内容]
  缓存键空间严格限定为 KV v2 secret 路径（即 vault_client.get 的结果）；
  Transit encrypt/decrypt 路径不经过 SecretCache，且其返回结果立即失效或丢弃。
[决策理由]
  - TDR-010 明确：解密明文禁缓存（避免重放窗口被拉长）
  - Vault Transit 密文自带 nonce，缓存无收益
  - 解耦使未来替换为 Vault Transit v2 不影响缓存层
[拒绝的替代方案]
  方案A: 全部缓存（包括密文/明文）— 拒绝理由：明文缓存违反 TDR-010 安全约束
  方案B: 用 M-D03 Redis 替代 — 拒绝理由：见 FDR-001
[影响范围] cache.py / vault_client.py
[相关FDR] FDR-M-C07-001
[来源标注] [DD-001:MD-M-C07 + TDR-010 + DD-M推断: 键空间分离]
```

## FDR-M-C07-003  拆分为 4 个文件而非 1 个大文件

```
[决策编号] FDR-M-C07-003
[决策标题] M-C07 文件结构采用 4 文件拆分
[决策状态] 已接受
[决策内容]
  按职责拆分为 vault_client.py / token_manager.py / transit.py / cache.py + __init__.py。
[决策理由]
  - 单一职责：每个文件一个协作者类
  - 测试隔离：单元测试可独立 Mock
  - 易于 Dev 阶段实现（多人协作）
[拒绝的替代方案]
  方案A: 单文件 secret.py — 拒绝理由：单文件函数数会超 20 上限（MD-M-C07 共有 ~21 个方法），违反 soul 4.2
  方案B: 7+ 文件细分 — 拒绝理由：过度拆分；M-C07 复杂度仅 4 个协作类，4 文件足矣
[影响范围] FS-016 / 全部框架文件
[相关FDR] -
[来源标注] [DD-001:FS-016/MD-M-C07 + soul 4.2]
```

## FDR-M-C07-004  续期策略 TTL-60s / Renew-300s

```
[决策编号] FDR-M-C07-004
[决策标题] TokenManager 续期策略
[决策状态] 已接受
[决策内容]
  默认动态 token TTL = 3600s；提前 300s 续期；renew 失败指数退避 1s/2s/4s（max 3）。
[决策理由]
  - Vault 默认 token TTL 32d，但业务层采用短期 token（[TD:S-026] 类似策略）
  - 5min 提前量提供充分容错（Vault 调用本身 < 500ms）
  - 3 次重试覆盖短暂网络抖动
[拒绝的替代方案]
  方案A: 永续期（依赖 Vault 自动回收）— 拒绝理由：丧失主动控制；运维不可见
  方案B: TTL=600s — 拒绝理由：续期频率过高，违反短期缓存初衷
[影响范围] token_manager.py
[相关FDR] -
[来源标注] [DD-001:MD-M-C07 + DD-M推断: TTL/重试参数]
```

## FDR-M-C07-005  fail-fast 启动策略

```
[决策编号] FDR-M-C07-005
[决策标题] Vault 不可用时启动失败
[决策状态] 已接受
[决策内容]
  应用启动期 health() 探测 Vault；若返回 sealed 或不可达，则拒绝启动并记录 ERROR。
[决策理由]
  - secret 是关键依赖；启动后才发现不可用会导致第一批请求全失败
  - fail-fast 触发 K8s 重启 → 触发告警 → 运维介入
[拒绝的替代方案]
  方案A: 启动后熔断降级 — 拒绝理由：secret 缺失会让 K4 / Approval / M-B05 全链路拒绝服务，影响面过大
  方案B: 启动时用 mock 占位 — 拒绝理由：违反"secret 必真"的安全约束
[影响范围] vault_client.py:health() / 启动序列
[相关FDR] -
[来源标注] [DD-001:MD-M-C07 + DD-M推断: fail-fast 启动模式]
```

## FDR-M-C07-006  命名：跨文件命名空间一致性

```
[决策编号] FDR-M-C07-006
[决策标题] 模块内命名空间避免与 M-D01 metadata 冲突
[决策状态] 已接受
[决策内容]
  本模块无 SQLAlchemy metadata 引用；如未来引入，需遵循 CS-MCP-V1.0 §1.5 别名约定：
  from sqlalchemy import MetaData as SAMetadata
[决策理由]
  - DD-001 洞察-6 已明确 SQLAlchemy MetaData 与本地 metadata 包同名易冲突
  - 本模块目前未涉及，预先记录以便演进
[拒绝的替代方案] n/a
[影响范围] 全模块
[相关FDR] -
[来源标注] [DD-001:DD洞察-6 + CS-MCP-V1.0 §1.5]
```
