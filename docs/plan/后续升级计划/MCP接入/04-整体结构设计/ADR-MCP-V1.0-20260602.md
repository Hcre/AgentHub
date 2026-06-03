# 架构决策记录 ADR-MCP-V1.0-20260602

> **范围**：8 条 ADR（[灵魂 R23] 100% 重大决策覆盖）

## ADR-001 架构模式选型

```
[决策编号] ADR-001
[决策标题] 主架构采用分层+事件驱动+插件化混合模式
[决策状态] 已接受
[决策内容] 主方案 = 分层架构（接入/应用/基础设施/数据）+ 事件总线（5 topic）+ 3 类 SPI（RuntimeInterface/ToolNameSpec/SandboxBackend）
[决策理由] 系统 4 业务主题耦合度中等；4 个事件触发点（审批/迁移/webhook/healthcheck）；MCP 市场+5 模板典型核心+扩展
[拒绝的替代方案] 微服务 5 服务（开发成本 +100%；K8s 运维复杂度高；沙箱+K4+SSRF 紧密耦合强行拆分引入分布式事务）
[影响范围] 全部 22 模块的依赖方向、接口契约、命名约束
[相关ADR] ADR-002/003/005
[来源标注] [SA:BR-001~035 业务规则 35 条 + CE-001~018 18 反例 + 调研 S-027/S-045]
```

## ADR-002 进程池 workspace 隔离

```
[决策编号] ADR-002
[决策标题] 进程池严格按 workspace 隔离（不提供跨 workspace 共享）
[决策状态] 已接受
[决策内容] 进程池 64/workspace 硬限（BR-005）；DB 主键 workspace_id + status 复合索引；mcpproxy per-MCP
[决策理由] 物理隔离避免资源争抢；满足 B-013 不处理边界；多 workspace 部署时 ulimit 风险可控
[拒绝的替代方案] 全局共享池（违反安全隔离 + 难以限流）
[影响范围] M-B02/M-D01/M-B05；部署单元按 workspace 划分
[相关ADR] —
[来源标注] [SA:BR-005 + 调研 S-042 + 物理视图 6,400 进程容量约束]
```

## ADR-003 事件总线选型

```
[决策编号] ADR-003
[决策标题] 事件总线采用 Redis Pub/Sub + 应用层 in-proc 订阅封装
[决策状态] 已接受
[决策内容] Redis Pub/Sub 作为跨进程通道；应用层封装 publish/subscribe 接口；5 个 topic：approval.*, template.*, process.*, mcp.*, binding.*
[决策理由] 复用现有 Redis 依赖；水平扩展可平滑切到 NATS/Kafka；in-proc 订阅降低应用复杂度
[拒绝的替代方案] Kafka（运维重 + 团队不熟）；NATS（新增依赖）；in-proc EventEmitter（仅单进程）
[影响范围] M-EV01 + 所有应用层模块
[相关ADR] ADR-001
[来源标注] [TD推断:基于部署视图 Redis 必选 + 团队技能]
```

## ADR-004 SSRF 5 层防御

```
[决策编号] ADR-004
[决策标题] Streamable HTTP 走 5 层 SSRF 防御
[决策状态] 已接受
[决策内容] yarl 单对象 Pin + 域名级缓存（DE-018）+ 重定向重校验 + IP 白名单 + DNSSEC
[决策理由] 单层 yarl Pin 跨对象失效（S-052）；5 层纵深防御在 CE-004 反例中得到验证
[拒绝的替代方案] 仅 yarl Pin（S-052 反例已证伪）；仅 IP 白名单（DNS rebind 失效）
[影响范围] M-C04/M-C06/M-B05
[相关ADR] —
[来源标注] [SA:BR-010/011 + CE-004 + EX-024/025]
```

## ADR-005 mcp-config 单一源

```
[决策编号] ADR-005
[决策标题] mcp-config 文件由 L4 单一生成器输出（覆盖 3 Runtime 最小公共子集）
[决策状态] 已接受
[决策内容] L4 generator 按 Runtime 类型输出 schema（5/8/4 层优先级）；SHARED LOCK 行级；路径固定 /tmp/agenthub/mcp-{agent_id}.json
[决策理由] 防 Claude Code 静默覆盖 OpenCode 用户配置（Bug #2946）；SHARED LOCK 跨进程有效
[拒绝的替代方案] 各 Runtime 独立生成（Bug #2946 重现）；分布式锁（增加复杂度）
[影响范围] M-B03/M-B05/M-C08
[相关ADR] —
[来源标注] [SA:BR-032 + 调研 S-023/S-024 + EX-016/017]
```

## ADR-006 allowlist 公共 hash 函数

```
[决策编号] ADR-006
[决策标题] 提取 compute_args_hash(args) 公共函数
[决策状态] 已接受
[决策内容] M-B04 内部公共函数 compute_args_hash（sorted_json + ensure_ascii=False + SHA256）；BP-019 写入与 BP-021 查询强制调用同一函数
[决策理由] CE-006 反例证伪：分散实现导致 ensure_ascii 偏差
[拒绝的替代方案] 各自实现（CE-006 重现）
[影响范围] M-B04
[相关ADR] —
[来源标注] [SA:CE-006 + BR-021]
```

## ADR-007 命名截断 8 字符碰撞升级

```
[决策编号] ADR-007
[决策标题] 6 字符 MD5 碰撞时升级到 8 字符后缀
[决策状态] 已接受
[决策内容] BP-008 步骤 7 增加碰撞检测：6 字符碰撞概率 1/16M；升级 8 字符碰撞概率 1/4B（可接受）
[决策理由] CE-016 反例：长命名场景下 1/16M 概率不可接受
[拒绝的替代方案] 直接用 8 字符（短命名场景冗余）
[影响范围] M-C08
[相关ADR] —
[来源标注] [SA:CE-016 + BR-004]
```

## ADR-008 Cron 相位错开

```
[决策编号] ADR-008
[决策标题] healthcheck 与 idle_scan 错开 15s 相位
[决策状态] 已接受
[决策内容] healthcheck 在 :00 周期 30s；idle_scan 在 :15/:45 周期 30s
[决策理由] CE-002 反例：同相位抢占 asyncio loop 导致 64 healthcheck 排队 5s+
[拒绝的替代方案] 串行调度（总周期变长 1 倍）；分离进程（增加运维）
[影响范围] M-A04
[相关ADR] —
[来源标注] [SA:CE-002 + BR-008]
```
