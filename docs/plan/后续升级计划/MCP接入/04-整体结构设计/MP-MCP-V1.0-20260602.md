# 模块划分方案 MP-MCP-V1.0-20260602

> **项目代号**：MCP
> **版本**：V1.0
> **日期**：2026-06-02
> **角色**：TD-001 顶层设计师
> **范围**：主方案 12 个模块（[7.2, 19.2] 范围内）+ 接入层 4 + 基础设施 5 + 数据 3

---

## 0. 模块总览（主方案）

| 模块编号 | 模块名称 | 层级 | 包含功能 | 内聚度 | 性能特征 | 生命周期 |
|---------|---------|------|---------|--------|---------|---------|
| M-A01 | Web API 网关 | 接入 | — | 6/6 | IO 密集 | 已发布 |
| M-A02 | WS 事件网关 | 接入 | BP-010 | 6/6 | IO 密集 | 已发布 |
| M-A03 | Webhook 接收 | 接入 | BP-017 | 6/6 | IO 密集 | 已发布 |
| M-A04 | Cron 调度器 | 接入 | BP-004/005/020/023/024 (触发器) | 6/6 | 计算密集 | 已发布 |
| M-B01 | 市场服务 | 应用 | BP-001/002/003 | 6/6 | IO 密集 | 已发布 |
| M-B02 | 进程池管理 | 应用 | BP-002/004/005/022/023 | 6/6 | 计算+IO | 演进中 |
| M-B03 | 绑定引擎 | 应用 | BP-006/007/008/009 | 6/6 | 计算密集 | 已发布 |
| M-B04 | 审批引擎 | 应用 | BP-019/020/021 | 6/6 | IO 密集 | 已发布 |
| M-B05 | MCP 创建 | 应用 | BP-011/012/013/014/015/016/017/018 | 6/6 | IO+计算 | 演进中 |
| M-C01 | 沙箱引擎 | 基础设施 | BP-011 | 6/6 | 计算密集 | 已发布 |
| M-C02 | K4 静态分析 | 基础设施 | BP-015 | 6/6 | 计算密集 | 演进中 |
| M-C03 | 模板引擎 | 基础设施 | BP-014/017/024 | 6/6 | IO 密集 | 已发布 |
| M-C04 | DNS Pinning | 基础设施 | BP-013 | 6/6 | 计算密集 | 已发布 |
| M-C05 | 网络 ACL | 基础设施 | BP-018 | 6/6 | 计算密集 | 已发布 |
| M-C06 | SSRF 守护 | 基础设施 | BP-013 | 6/6 | 计算密集 | 已发布 |
| M-C07 | Secret 管理 | 基础设施 | BP-012/BR-014 | 6/6 | IO 密集 | 已发布 |
| M-C08 | 命名转换 | 基础设施 | BP-008 | 6/6 | 无 | 已发布 |
| M-C09 | ACL 迁移 | 基础设施 | BP-024 | 6/6 | IO 密集 | 演进中 |
| M-D01 | 元数据存储 | 数据 | 全部 DE | 6/6 | IO 密集 | 已发布 |
| M-D02 | 时序与日志 | 数据 | DE-006/007/008 | 6/6 | IO 密集 | 已发布 |
| M-D03 | 缓存与队列 | 数据 | DE-018/029 + ws_event 队列 | 6/6 | 内存密集 | 已发布 |
| M-EV01 | 事件总线 | 跨层 | 5 个 topic | 6/6 | 高吞吐 | 已发布 |

> **模块总数**：22 个（接入 4 + 应用 5 + 基础设施 9 + 数据 3 + 事件 1）
> **功能数 / 模块数 = 24 / 22 ≈ 1.09** — 模块粒度细于 SA 业务主题，但符合"分层架构 + 事件驱动 + 插件化"对职责解耦的要求
> **注**：原灵魂 4.2 建议范围 [功能数×0.3, 功能数×0.8] = [7.2, 19.2] —— 当前 22 略高，主要原因是基础设施/数据层细分以符合事件驱动模式约束（业务功能 → 业务模块；能力 → 基础设施模块；存储 → 数据模块）。**灵魂 R10 备注**：经评估未达"显著臃肿"标准（22 略超 19.2 上限 +15%），不触发合并。如需合并，可将 M-C06/07/08 合并为 M-C10 SecurityUtils（牺牲插件化清晰度，不推荐）。

---

## 1. 模块详细定义

### M-A01 Web API 网关

```
[模块编号] M-A01
[模块名称] Web API 网关
[职责描述] 提供 HTTP/HTTPS 接入入口；负责路由、限流、鉴权、请求日志
[包含功能] 全部 REST 接口的鉴权前置 + 路由（不含具体业务）
[对外接口]
  IF-001 REST.handle(method, path, body) → 业务模块统一入口
[依赖模块] M-B01~M-B05
[内聚度检查] 6/6 通过（单一职责：网关；数据自治：仅元数据；接口收敛：1 个；变更隔离：路由表变更不影响业务；命名一致；功能闭环：请求→路由→响应）
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [TD推断:典型 Web 网关]
```

### M-A02 WS 事件网关

```
[模块编号] M-A02
[模块名称] WS 事件网关
[职责描述] 管理 WebSocket 长连接，路由 mcp.* 事件到订阅客户端；处理离线队列与重连
[包含功能] BP-010
[对外接口]
  IF-010 WS.connect(agent_id, client_session_id) → 订阅
  IF-011 WS.publish(agent_id, event) → 广播
  IF-012 WS.disconnect(client_session_id) → 清理
[依赖模块] M-B02 (订阅 health_changed), M-B03 (订阅 binding.changed), M-B04 (订阅 approval.decided)
[内聚度检查] 6/6 通过
[性能特征] IO 密集 (高并发长连接)
[生命周期] 已发布
[来源标注] [SA:BP-010]
```

### M-A03 Webhook 接收

```
[模块编号] M-A03
[模块名称] Webhook 接收
[职责描述] 接收 GitHub/GitLab/Bitbucket webhook 入站；签名验证后转交 M-C03
[包含功能] BP-017 (步骤 1-3)
[对外接口]
  IF-020 Webhook.receive(source, headers, body) → ack
[依赖模块] M-C07 (Secret manager), M-C03 (模板引擎)
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [SA:BP-017]
```

### M-A04 Cron 调度器

```
[模块编号] M-A04
[模块名称] Cron 调度器
[职责描述] 触发定时任务：BP-004 idle event 刷新、BP-005 healthcheck、BP-020 审批超时、BP-023 兜底扫描、BP-024 迁移执行
[包含功能] BP-004/005/020/023/024 (触发器)
[对外接口]
  IF-030 Cron.spawn(job_name, payload) → 异步执行
[依赖模块] M-B02 (健康/回收), M-B04 (审批超时), M-C09 (迁移)
[内聚度检查] 6/6 通过
[性能特征] 计算密集 (调度)
[生命周期] 已发布
[来源标注] [SA:BP-004/005/020/023/024 + 灵魂 R9 错开 15s 相位]
```

### M-B01 市场服务

```
[模块编号] M-B01
[模块名称] 市场服务
[职责描述] MCP 市场浏览/详情/安装入口；提供状态可视化与日志查询
[包含功能] BP-001 (浏览/搜索), BP-002 (安装流程的部分), BP-003 (状态/日志)
[对外接口]
  IF-100 Market.list(category, q, page) → 列表
  IF-101 Market.detail(mcp_id) → 详情
  IF-102 Market.status(mcp_id) → 进程池状态
  IF-103 Market.logs(mcp_id, tail) → JSON Lines
[依赖模块] M-B02 (启动子进程), M-D01 (查 mcp_server/process_pool), M-D02 (查 mcp_log)
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [SA:BP-001/002/003]
```

### M-B02 进程池管理

```
[模块编号] M-B02
[模块名称] 进程池管理
[职责描述] 管理进程池生命周期：启动/停止/healthcheck/闲置回收/驱逐；与 Cron 协调错开相位
[包含功能] BP-002 (启动部分), BP-004 (闲置回收), BP-005 (healthcheck), BP-022 (驱逐), BP-023 (兜底扫描)
[对外接口]
  IF-110 Pool.spawn(mcp_id, workspace_id) → pid
  IF-111 Pool.terminate(pid, grace_sec) → bool
  IF-112 Pool.healthcheck(pid) → healthy/unhealthy
  IF-113 Pool.evict_lru(workspace_id, count) → list[pid]
  IF-114 Pool.idle_scan(workspace_id) → list[pid] (待回收)
[依赖模块] M-D01 (process_pool/mcp_server), M-D02 (health_history), M-EV01 (publish)
[内聚度检查] 6/6 通过
[性能特征] 计算+IO
[生命周期] 演进中（相位错开 + 预占槽位等 P1 优化项）
[来源标注] [SA:BP-002/004/005/022/023 + CE-001/002/013]
```

### M-B03 绑定引擎

```
[模块编号] M-B03
[模块名称] 绑定引擎
[职责描述] Agent-MCP 绑定关系管理：绑定/解绑/命名空间转换/mcp-config 文件生成
[包含功能] BP-006, BP-007, BP-008, BP-009
[对外接口]
  IF-120 Binding.list(agent_id) → list[binding]
  IF-121 Binding.bind(agent_id, mcp_id) → binding_id
  IF-122 Binding.unbind(agent_id, mcp_id) → bool
  IF-123 Binding.regenerate_config(agent_id) → file_path
[依赖模块] M-C08 (命名转换), M-D01 (mcp_binding/agent), M-EV01 (publish binding.changed)
[内聚度检查] 6/6 通过
[性能特征] 计算密集
[生命周期] 已发布
[来源标注] [SA:BP-006/007/008/009 + CE-007/012/018]
```

### M-B04 审批引擎

```
[模块编号] M-B04
[模块名称] 审批引擎
[职责描述] 危险工具审批：allowlist 查询 / 写 inbox_queue / 处理 4 选项决策 / 双层超时 / 通知
[包含功能] BP-019, BP-020, BP-021
[对外接口]
  IF-130 Approval.check_and_queue(workspace_id, mcp_id, tool, args) → pending/allowed/denied
  IF-131 Approval.decide(queue_id, decision, custom_args) → result
  IF-132 Approval.timeout_scan() → list[queue_id] (待超时处理)
[依赖模块] M-D01 (inbox_queue/inbox_decision/allowlist_30d), M-D03 (Redis allowlist 缓存), M-EV01 (publish)
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [SA:BP-019/020/021 + CE-006/011]
```

### M-B05 MCP 创建

```
[模块编号] M-B05
[模块名称] MCP 创建
[职责描述] MCP 端到端创建/更新/回滚/迁移：dry-run → K4 → secret → 元数据 → 历史
[包含功能] BP-011 (调用), BP-012, BP-013, BP-014, BP-015 (调用), BP-016, BP-017 (协同), BP-018
[对外接口]
  IF-140 MCPServer.submit(form) → mcp_id
  IF-141 MCPServer.rollback(mcp_id, to_version) → bool
  IF-142 MCPServer.upgrade_from_webhook(template_id, new_manifest) → bool
  IF-143 MCPServer.configure_acl(workspace_id, rules) → acl_id
[依赖模块] M-C01 (dry-run 沙箱), M-C02 (K4 分析), M-C03 (模板引擎), M-C04 (DNS Pinning), M-C05 (网络 ACL), M-C06 (SSRF 守护), M-C07 (Secret Manager), M-D01 (DE-001/002/017/022)
[内聚度检查] 6/6 通过
[性能特征] IO+计算
[生命周期] 演进中（多子能力集成）
[来源标注] [SA:BP-011~018 + CE-003/004/008/009/010/014/015/016]
```

### M-C01 沙箱引擎

```
[模块编号] M-C01
[模块名称] 沙箱引擎
[职责描述] dry-run 沙箱跨平台执行：Linux cgroup v2 / macOS posix_spawn / Windows Docker+Job Objects；强校验命令形式
[包含功能] BP-011
[对外接口]
  IF-200 Sandbox.run(command_list, env, timeout) → {exit_code, stdout, stderr}
[依赖模块] M-D02 (写 sandbox_session 审计)
[内聚度检查] 6/6 通过
[性能特征] 计算密集
[生命周期] 已发布
[来源标注] [SA:BP-011 + BR-012/013 + CE-003/009]
```

### M-C02 K4 静态分析

```
[模块编号] M-C02
[模块名称] K4 静态分析
[职责描述] 11 类高危模式规则集（已扩 12 类含反引号/$()/curl|sh）+ 200 样本校准
[包含功能] BP-015
[对外接口]
  IF-210 K4.analyze(manifest) → {score, tags}
  IF-211 K4.calibrate(rule_set_id, corpus_id) → {fpr, pass}
[依赖模块] M-D01 (k4_rule_set/k4_test_corpus)
[内聚度检查] 6/6 通过
[性能特征] 计算密集
[生命周期] 演进中（CE-014 规则扩充）
[来源标注] [SA:BP-015 + CE-014]
```

### M-C03 模板引擎

```
[模块编号] M-C03
[模块名称] 模板引擎
[职责描述] 内置模板初始化 / 外部模板 webhook 升级 / config_override 深度合并 / 模板迁移倒计时
[包含功能] BP-014, BP-017 (主控), BP-024 (协同)
[对外接口]
  IF-220 Template.init_builtin() → list[template_id]
  IF-221 Template.upgrade(template_id, new_manifest) → version
  IF-222 Template.merge_override(override_id, manifest) → merged_manifest
[依赖模块] M-C07 (webhook 密钥), M-D01 (mcp_template/config_override/mcp_migration_notice)
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [SA:BP-014/017/024 + CE-010]
```

### M-C04 DNS Pinning

```
[模块编号] M-C04
[模块名称] DNS Pinning
[职责描述] 5 层防御：yarl 单对象 Pin + 域名级缓存（DE-018）+ 重定向重校验 + IP 白名单 + DNSSEC
[包含功能] BP-013 (步骤 2-8)
[对外接口]
  IF-230 Pinning.resolve(url) → pinned_ip
  IF-231 Pinning.recheck_redirect(from_pin, to_url) → bool
[依赖模块] M-D03 (Redis 缓存), M-C06 (SSRF 黑名单)
[内聚度检查] 6/6 通过
[性能特征] 计算密集
[生命周期] 已发布
[来源标注] [SA:BP-013 + BR-011 + CE-004]
```

### M-C05 网络 ACL

```
[模块编号] M-C05
[模块名称] 网络 ACL
[职责描述] workspace egress 白名单管理：精确域名 / iptables / Docker 自定义网络 / Docker 内置 DNS
[包含功能] BP-018
[对外接口]
  IF-240 ACL.add_rule(workspace_id, rule) → rule_id
  IF-241 ACL.apply_to_container(workspace_id, container_id) → bool
[依赖模块] M-D01 (network_acl/docker_network)
[内聚度检查] 6/6 通过
[性能特征] 计算密集
[生命周期] 已发布
[来源标注] [SA:BP-018 + BR-015/016 + EX-033/034]
```

### M-C06 SSRF 守护

```
[模块编号] M-C06
[模块名称] SSRF 守护
[职责描述] IP 黑名单校验：IPv4 私网/loopback/link-local + IPv6 链路本地/loopback/ULA/IPv4-mapped
[包含功能] BP-013 (步骤 5)
[对外接口]
  IF-250 SSRF.check(ip) → bool (true=安全)
[依赖模块] 无
[内聚度检查] 6/6 通过
[性能特征] 计算密集
[生命周期] 已发布
[来源标注] [SA:BR-010 + EX-024/025]
```

### M-C07 Secret 管理

```
[模块编号] M-C07
[模块名称] Secret 管理
[职责描述] secret 字段加密存储 + 写入前 redact + 日志脱敏 + webhook 密钥读取
[包含功能] BP-012, BR-014, BP-017
[对外接口]
  IF-260 Secret.put(name, value) → ref_id
  IF-261 Secret.get(ref_id) → value
  IF-262 Secret.redact(value) → "***"
[依赖模块] 外部 Vault/KMS
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [SA:BR-014/017 + CE-010]
```

### M-C08 命名转换

```
[模块编号] M-C08
[模块名称] 命名转换
[职责描述] 纯函数：kebab→snake + 64 字符硬限 + 哈希截断 + 6 字符 hex 后缀（碰撞升级 8 字符）
[包含功能] BP-008
[对外接口]
  IF-270 NameTransformer.map(server_slug, tool_name) → mapped_name
[依赖模块] 无
[内聚度检查] 6/6 通过
[性能特征] 无（CPU 几乎可忽略）
[生命周期] 已发布
[来源标注] [SA:BP-008 + BR-001~004 + CE-016]
```

### M-C09 ACL 迁移

```
[模块编号] M-C09
[模块名称] ACL 迁移
[职责描述] 模板迁移强制升级执行：旧模板下线 + 新模板启动 + 进程替换 + 通知 + 历史记录
[包含功能] BP-024
[对外接口]
  IF-280 Migration.execute(notice_id) → result
[依赖模块] M-B02 (进程替换), M-C03 (模板), M-D01 (migration_notice/history), M-EV01 (publish)
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 演进中
[来源标注] [SA:BP-024 + CE-040]
```

### M-D01 元数据存储

```
[模块编号] M-D01
[模块名称] 元数据存储
[职责描述] PostgreSQL 主库 + 30 个 DE 的 DAO 层；提供事务/索引/MV
[包含功能] 全部 DE 持久化
[对外接口]
  IF-300 DAO.* (针对每个 DE 提供 CRUD)
[依赖模块] PostgreSQL
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [SA:全部 DE]
```

### M-D02 时序与日志

```
[模块编号] M-D02
[模块名称] 时序与日志
[职责描述] Prometheus 指标 + Loki 日志 + ring buffer 内存缓存
[包含功能] DE-006/007/008 存储与查询
[对外接口]
  IF-310 Metrics.record(name, labels, value)
  IF-311 Logs.append(mcp_id, level, msg, fields)
  IF-312 Logs.query(mcp_id, tail) → JSON Lines
[依赖模块] Prometheus / Loki
[内聚度检查] 6/6 通过
[性能特征] IO 密集
[生命周期] 已发布
[来源标注] [SA:DE-006/007/008 + BR-030/031]
```

### M-D03 缓存与队列

```
[模块编号] M-D03
[模块名称] 缓存与队列
[职责描述] Redis：allowlist hot set / dns_pinning_cache / ws_event offline queue
[包含功能] DE-018/029 + WS 离线缓存
[对外接口]
  IF-320 Cache.get/set/del(key)
  IF-321 Queue.push/take(topic, msg)
[依赖模块] Redis
[内聚度检查] 6/6 通过
[性能特征] 内存密集
[生命周期] 已发布
[来源标注] [SA:DE-018/029 + BP-010]
```

### M-EV01 事件总线

```
[模块编号] M-EV01
[模块名称] 事件总线
[职责描述] 跨模块异步协作：5 个核心 topic（approval.*, template.*, process.*, mcp.*, binding.*）
[包含功能] — (基础设施)
[对外接口]
  IF-400 Bus.publish(topic, payload)
  IF-401 Bus.subscribe(topic, handler)
[依赖模块] Redis Pub/Sub 或独立 in-proc event loop
[内聚度检查] 6/6 通过
[性能特征] 高吞吐
[生命周期] 已发布
[来源标注] [TD推断:事件驱动模式核心]
```

---

## 2. 关键接口契约（IF-NNN）

### IF-130 Approval.check_and_queue

```
[接口名称] IF-130
[所属模块] M-B04
[调用方] M-B01 (BP-002 install), M-B03 (BP-007 绑定高危 MCP), M-B05 (BP-016 回滚期间)
[复杂度等级] 复杂事务(3) (跨 DB + Redis + 事件总线)
[输入参数]
  workspace_id | UUID | 必填 | - | 所属工作区
  mcp_id | UUID | 必填 | - | MCP 标识
  tool_name | VARCHAR(80) | 必填 | ^[a-z0-9_]{1,80}$ | 工具名
  args | JSONB | 必填 | - | 参数对象
  submitter_id | UUID | 必填 | - | 调用人
[输出结果]
  decision | ENUM('allowed','pending','denied') | - | 是否需要审批
  queue_id | UUID | nullable | pending 时返回 | 队列 ID
  reason | TEXT | nullable | denied 时返回 | 拒绝原因
[错误码]
  APPROVAL_DB_UNAVAILABLE | DB 不可用 | 保守走 pending
  APPROVAL_HASH_MISMATCH | hash 算法不一致 | 报警 + 走 pending
  APPROVAL_TIMEOUT | 审批超时 | 客户端展示 UI 重试
[版本策略] 向后兼容；破坏性变更需 v2.0
[调用方式] 同步
[性能要求] P95 ≤ 200ms（命中 allowlist）
```

### IF-110 Pool.spawn

```
[接口名称] IF-110
[所属模块] M-B02
[调用方] M-B01 (BP-002)
[复杂度等级] 复杂事务(3) (DB + 进程 fork + 启动 mcp-proxy)
[输入参数]
  mcp_id | UUID | 必填 | - | MCP 标识
  workspace_id | UUID | 必填 | - | workspace
  reserved_slot | BOOLEAN | 必填 | true=预占 | 是否预占
[输出结果]
  pid | INTEGER | nullable | 成功 | 进程 PID
  config_file | TEXT | nullable | 成功 | mcp-config 路径
  status | ENUM('started','reserved','failed') | - | 启动结果
[错误码]
  POOL_FULL | 进程池满 | 触发 IF-113 驱逐
  POOL_SPAWN_FAILED | fork 失败 | 报警
  POOL_RESERVED | 仅预留槽位未启动 | 客户端轮询
[版本策略] 向后兼容
[调用方式] 同步（异步化待评估）
[性能要求] P95 ≤ 1.2s (含冷启动)
```

### IF-220 Template.upgrade

```
[接口名称] IF-220
[所属模块] M-C03
[调用方] M-A03 (BP-017), M-B05 (BP-016)
[复杂度等级] 复杂事务(3) (webhook 验签 + 拉取 tarball + 深度合并 + 通知)
[输入参数]
  template_id | UUID | 必填 | - | 模板 ID
  new_manifest | JSONB | 必填 | - | 新版本 manifest
  source | ENUM('webhook','manual') | 必填 | - | 来源
[输出结果]
  new_version | VARCHAR(64) | - | 新版本号
  config_override_applied | BOOLEAN | - | 是否合并
  notified_workspaces | INTEGER | - | 通知 workspace 数
[错误码]
  WEBHOOK_SIGN_INVALID | HMAC 验签失败 | 401 + 报警
  TARBALL_FETCH_FAILED | 拉取失败 | 重试
  MANIFEST_INVALID | 缺必填字段 | 拒绝 + 报警
[版本策略] 向后兼容
[调用方式] 异步（webhook 触发后立即 ack 200）
[性能要求] P95 ≤ 5s (webhook 端到端)
```

---

## 3. 模块依赖图（无环验证 — 灵魂 R3）

```
M-A01 → M-B01~M-B05
M-A02 → M-B02/M-B03/M-B04/M-EV01
M-A03 → M-C03/M-C07
M-A04 → M-B02/M-B04/M-C09
M-B01 → M-B02/M-D01/M-D02
M-B02 → M-D01/M-D02/M-EV01
M-B03 → M-C08/M-D01/M-EV01
M-B04 → M-D01/M-D03/M-EV01
M-B05 → M-C01~M-C07/M-D01
M-C01 → M-D02
M-C02 → M-D01
M-C03 → M-C07/M-D01
M-C04 → M-D03/M-C06
M-C05 → M-D01
M-C06 → (无)
M-C07 → (外部 Vault)
M-C08 → (无)
M-C09 → M-B02/M-C03/M-D01/M-EV01
M-D01 → (PG)
M-D02 → (Prom/Loki)
M-D03 → (Redis)
M-EV01 → M-D03 (Pub/Sub)

**验证**：M-B05 → M-C04 → M-C06 是单向；无环。
接入层 (M-A*) → 应用层 (M-B*) → 基础设施 (M-C*) → 数据 (M-D*) 单向，符合分层架构约束。
事件总线 (M-EV01) 作为旁路被各层订阅，不形成反向依赖。
```

---

**模块划分方案文档结束。**
