# 技术决策记录 TDR-MCP-V1.0-20260602

> **范围**：10 项重大技术决策（TDR-001 ~ TDR-010），全部含决策理由 + 拒绝的替代方案 + 影响范围

---

## TDR-001 核心技术栈选 Python 3.11 + FastAPI

```
[决策编号] TDR-001
[决策标题] 核心技术栈采用 Python 3.11 + FastAPI
[决策状态] 已接受
[决策内容]
  核心语言: Python 3.11.x
  Web 框架: FastAPI 0.109.x + Uvicorn 0.27.x
  ORM: SQLAlchemy 2.0.25.x 异步 + asyncpg
[决策理由]
  - 团队 Python 熟练度 > Go > Node.js (内部调研)
  - 业务逻辑复杂度高 (24 BP / 30 DE), Python 表达力强
  - 沙箱跨平台 (Windows Job Objects / macOS posix_spawn) 需 ctypes/pywin32, Python 已有现成绑定
  - AI/ML 集成 (M-C02 K4 后续 LLM 增强) Python 生态优势
  - 6 项合理性检查全部通过
[拒绝的替代方案]
  - Go 1.22: 团队不熟 (学习曲线 1-2 月), 沙箱跨平台需重写, 拒绝
  - Node.js 20: CPU 密集型 (M-C01/M-C02) 不优, type system 弱, 拒绝
  - Rust: 学习曲线 > 3 月, 生态不成熟, 拒绝
[影响范围] 全部 22 模块
[相关TDR] TDR-002/003/008/009
[来源标注] [TD:ADR-001] [调研:R-003 沙箱跨平台] [AR推断:团队栈匹配]
```

## TDR-002 事件总线采用 Redis Pub/Sub

```
[决策编号] TDR-002
[决策标题] 事件总线选 Redis Pub/Sub + in-proc emitter 兜底
[决策状态] 已接受
[决策内容]
  跨进程: Redis 7.2 Pub/Sub (5 topic: approval.* / template.* / process.* / mcp.* / binding.*)
  进程内: asyncio.Event + in-proc emitter (兜底)
[决策理由]
  - 复用现有 Redis 依赖 (M-D03)
  - 团队 Redis 熟练度高
  - in-proc emitter 降低单进程模块的复杂度
  - 水平扩展时可平滑切换到 NATS/Kafka
[拒绝的替代方案]
  - Kafka: 运维重 (ZooKeeper/KRaft), 团队不熟, 拒绝
  - NATS: 新增依赖, 团队不熟, 拒绝
  - 纯 in-proc EventEmitter: 仅单进程, 拒绝
  - RabbitMQ: 功能冗余 (我们用不到 AMQP 完整特性), 拒绝
[影响范围] M-EV01 + 全部应用层模块 (5 topic)
[相关TDR] TDR-001
[来源标注] [TD:ADR-003] [AR推断:复用 Redis 降低运维负担]
```

## TDR-003 进程池 workspace 隔离

```
[决策编号] TDR-003
[决策标题] 进程池严格按 workspace 隔离 (64/workspace 硬限)
[决策状态] 已接受
[决策内容]
  进程池: 64/workspace 硬限 (BR-005)
  DB 主键: workspace_id + status 复合索引
  mcp-proxy: per-MCP 独立子进程
  部署: workspace = K8s namespace
[决策理由]
  - 物理隔离避免资源争抢
  - 满足 B-013 不处理边界 (跨 ws 共享)
  - 多 workspace 部署时 ulimit 风险可控
  - 单 workspace 故障不影响全局
[拒绝的替代方案]
  - 全局共享池: 违反安全隔离, 限流困难, 拒绝
  - 软限: 难以容量规划, 拒绝
  - 动态调整: 复杂度高, V1.0 不必要, 拒绝
[影响范围] M-B02/M-D01/M-B05 + 部署按 workspace 划分
[相关TDR] TDR-001
[来源标注] [TD:ADR-002] [调研:RSK-02 6,400 容量]
```

## TDR-004 SSRF 5 层防御

```
[决策编号] TDR-004
[决策标题] Streamable HTTP 走 5 层 SSRF 防御
[决策状态] 已接受
[决策内容]
  Layer 1: yarl 单对象 Pin (M-C04)
  Layer 2: 域名级缓存 (DE-018, TTL 60s)
  Layer 3: 重定向重校验 (max 3 跳)
  Layer 4: IP 白名单 (M-C06 frozenset O(1))
  Layer 5: DNSSEC 验证 (可选, V2.0)
[决策理由]
  - 单层 yarl Pin 跨对象失效 (S-052 反例)
  - 5 层纵深防御在 CE-004 反例中验证
  - OWASP SSRF Prevention Cheat Sheet 推荐
  - 已知绕过 (xip.io / hex / IPv6) 全部覆盖
[拒绝的替代方案]
  - 仅 yarl Pin: S-052 反例已证伪, 拒绝
  - 仅 IP 白名单: DNS rebind 失效, 拒绝
  - 商业 SSRF 防护服务: 成本高, 拒绝
[影响范围] M-C04/M-C06/M-B05
[相关TDR] —
[来源标注] [TD:ADR-004] [调研:R-009 + S-032/S-033]
```

## TDR-005 mcp-config L4 单一源

```
[决策编号] TDR-005
[决策标题] mcp-config 文件由 L4 单一生成器输出
[决策状态] 已接受
[决策内容]
  生成器: M-B03 唯一生成器 (L4 layer)
  输出: 5/8/4 层优先级 schema 覆盖 3 Runtime 最小公共子集
  锁: fcntl SHARED LOCK 行级
  路径: /tmp/agenthub/mcp-{agent_id}.json (固定)
  权限: 0600
[决策理由]
  - 防止 Claude Code 静默覆盖 OpenCode 用户配置 (Bug #2946)
  - SHARED LOCK 跨进程有效
  - 路径固定防止路径遍历
[拒绝的替代方案]
  - 各 Runtime 独立生成: Bug #2946 重现, 拒绝
  - 分布式锁 (etcd): 增加复杂度, V1.0 不必要, 拒绝
  - 软链接: race condition, 拒绝
[影响范围] M-B03/M-B05/M-C08
[相关TDR] —
[来源标注] [TD:ADR-005] [调研:S-023/S-024 + RSK-08]
```

## TDR-006 allowlist 公共 hash 函数

```
[决策编号] TDR-006
[决策标题] 提取 compute_args_hash(args) 公共函数
[决策状态] 已接受
[决策内容]
  函数: compute_args_hash(args)
  实现: sorted_json + ensure_ascii=False + SHA256
  调用: BP-019 写入与 BP-021 查询强制调用同一函数
  位置: M-B04 内部
[决策理由]
  - CE-006 反例证伪: 分散实现导致 ensure_ascii 偏差
  - 中文参数 (ensure_ascii=False) 是关键, 一致性是正确性前提
  - 公共函数强制调用, 编译期检查
[拒绝的替代方案]
  - 各自实现: CE-006 重现, 拒绝
  - 哈希字典 (json.dumps 默认): 中文字符偏差, 拒绝
  - 业务层 hash: 业务模块耦合, 拒绝
[影响范围] M-B04
[相关TDR] —
[来源标注] [TD:ADR-006] [调研:CE-006 + BR-021]
```

## TDR-007 命名 6→8 字符碰撞升级

```
[决策编号] TDR-007
[决策标题] 6 字符 MD5 碰撞时升级到 8 字符后缀
[决策状态] 已接受
[决策内容]
  默认: 6 字符 hex 后缀 (碰撞概率 1/16M)
  升级: 8 字符 (碰撞概率 1/4B, 可接受)
  触发: 6 字符碰撞检测时自动升级
[决策理由]
  - CE-016 反例: 长命名场景下 1/16M 不可接受
  - 8 字符 1/4B 概率对 V1.0 业务规模可接受
  - 自适应避免短命名冗余
[拒绝的替代方案]
  - 直接 8 字符: 短命名场景冗余, 拒绝
  - 12 字符: 过度设计, 拒绝
  - UUID 后缀: 不可读, 拒绝
[影响范围] M-C08
[相关TDR] —
[来源标注] [TD:ADR-007] [调研:CE-016 + BR-004]
```

## TDR-008 沙箱跨平台 4 后端自适应

```
[决策编号] TDR-008
[决策标题] 沙箱跨平台 4 后端自适应 (Linux cgroup v2 / macOS posix_spawn / Windows Job Objects / Docker)
[决策状态] 已接受
[决策内容]
  Linux: cgroup v2 pids.max (避免影响父进程)
  macOS: subprocess.run(preexec_fn=...) + 显式 posix_spawn
  Windows 原生: pywin32 Job Objects
  Windows Docker: Docker 24+ + WSL2 (fallback)
  降级: setrlimit (CPU/内存限制, 失去 pids 隔离)
[决策理由]
  - 调研 R-003 验证 4 后端完全可行
  - Linux setrlimit RLIMIT_NPROC 会同时限制父进程, 必须改用 cgroup v2
  - macOS sandbox-exec 有版本差异, 走 posix_spawn 更稳定
  - Windows 无 Docker 时 pywin32 纯 Python 绑定, 无 C 扩展
[拒绝的替代方案]
  - 仅 Docker: 跨平台支持弱, V1.0 不接受, 拒绝
  - 仅 setrlimit: Linux pids 隔离失效, 拒绝
  - Firecracker/gVisor: 重, V1.0 不必要, 拒绝
[影响范围] M-C01
[相关TDR] TDR-001
[来源标注] [调研:R-003 + S-025 + S-026 CVE-2025-53372]
```

## TDR-009 K4 走独立 gRPC 服务

```
[决策编号] TDR-009
[决策标题] K4 静态分析走独立 gRPC 服务 (8 worker pool)
[决策状态] 已接受
[决策内容]
  协议: gRPC (Protocol Buffers) over HTTP/2
  部署: 独立 Deployment, 1 实例 + 8 worker subprocess
  序列化: Protobuf 3
  鉴权: mTLS (内部服务间)
[决策理由]
  - K4 是 CPU 密集型, 不应占用 agenthub-core 主进程
  - 8 worker 并行加速分析 (P95 < 10s 目标)
  - 独立扩缩容 (K8s Deployment)
  - 规则集内存常驻, 避免每次加载
[拒绝的替代方案]
  - in-proc 同步: 阻塞主进程, 拒绝
  - HTTP REST: 序列化开销大, 拒绝
  - 消息队列异步: 引入额外组件, 拒绝
[影响范围] M-C02 + M-B05 编排
[相关TDR] TDR-001
[来源标注] [调研:R-008 K4 校准 + 误判率 15%]
```

## TDR-010 Vault Transit 自动轮换 90d

```
[决策编号] TDR-010
[决策标题] Vault Transit 引擎自动轮换 90d + auto-unseal
[决策状态] 已接受
[决策内容]
  引擎: Vault Transit (AES-256-GCM)
  轮换: 90d 自动 (Vault built-in)
  Unseal: auto-unseal (AWS KMS / GCP CKMS, 生产)
  Fallback: 静态密钥 (本地, dev/staging)
  启动: root token 启动时获取 → 短期 dynamic token
[决策理由]
  - OWASP 合规要求密钥定期轮换
  - auto-unseal 避免重启时人工 unseal
  - Transit 比静态加密更易管理 (集中轮换 + 审计)
[拒绝的替代方案]
  - 静态加密 (本地): 密钥管理分散, 拒绝
  - AWS KMS 直连 (绕开 Vault): 失去统一管理, 拒绝
  - 180d 轮换: 过长, 不符合合规, 拒绝
  - 不轮换: 安全风险, 拒绝
[影响范围] M-C07 + 全部依赖 secret 的模块
[相关TDR] —
[来源标注] [AR推断:OWASP 合规 + 部署降级路径]
```

---

## TDR 决策矩阵

| 编号 | 决策标题 | 状态 | 影响范围 | 关联模块数 |
|------|---------|------|---------|----------|
| TDR-001 | Python 3.11 + FastAPI 核心栈 | 已接受 | 全部 | 22 |
| TDR-002 | Redis Pub/Sub 事件总线 | 已接受 | 应用层 | 5 |
| TDR-003 | workspace 进程池隔离 | 已接受 | 部署 + 数据 | 3 |
| TDR-004 | SSRF 5 层防御 | 已接受 | 基础设施 | 3 |
| TDR-005 | mcp-config L4 单一源 | 已接受 | 应用 + 基础设施 | 3 |
| TDR-006 | allowlist 公共 hash 函数 | 已接受 | 应用层 | 1 |
| TDR-007 | 命名 6→8 字符升级 | 已接受 | 基础设施 | 1 |
| TDR-008 | 沙箱 4 后端自适应 | 已接受 | 基础设施 | 1 |
| TDR-009 | K4 独立 gRPC 服务 | 已接受 | 基础设施 | 2 |
| TDR-010 | Vault Transit 90d 轮换 | 已接受 | 基础设施 | 全部 |

**TDR 覆盖率：10/10 重大技术决策 100% ✓**

---

**技术决策记录文档结束。**
