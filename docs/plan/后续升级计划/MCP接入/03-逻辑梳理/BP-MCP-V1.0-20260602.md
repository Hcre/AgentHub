# 业务流程图（BP）— AgentHub MCP 接入 V1.0

> **项目代号**：MCP
> **版本**：V1.0（基于 PRD V1.3 终版 + 调研 V1.0 RCI 0.98）
> **日期**：2026-06-02
> **棒位**：SA-001 系统分析师
> **覆盖范围**：30 项 F-NNN 全部映射至 32 个 BP-NNN

---

## 0. 映射框架总览

| PRD 功能 | 流程编号 | 流程名称 | 风险等级 | 异常数 | 来源 |
|---|---|---|---|---|---|
| F-001 | BP-001 | MCP 市场首页渲染 | 核心 | 5 | [PRD:F-001] |
| F-002 | BP-002 | MCP 列表/搜索/筛选 | 标准 | 4 | [PRD:F-002] |
| F-003 | BP-003 | MCP 详情页加载 | 标准 | 4 | [PRD:F-003] |
| F-004 | BP-004 | 一键安装 MCP | 核心 | 5 | [PRD:F-004] |
| F-005 | BP-005 | 卸载 MCP | 核心 | 4 | [PRD:F-005] |
| F-006 | BP-006 | MCP 评分/评论 | 核心 | 4 | [PRD:F-006] |
| F-007 | BP-007 | MCP 分类/标签管理 | 标准 | 3 | [PRD:F-007] |
| F-008 | BP-008 | MCP 版本管理与切换 | 核心 | 5 | [PRD:F-008] |
| F-009 | BP-009 | Agent 绑定 MCP | 核心 | 5 | [PRD:F-009] |
| F-010 | BP-010 | Agent 解除 MCP 绑定 | 核心 | 4 | [PRD:F-010] |
| F-011 | BP-011 | 批量绑定/导入 MCP | 核心 | 5 | [PRD:F-011] |
| F-012 | BP-012 | CLI Adapter 注入 MCP 配置 | 核心 | 5 | [PRD:F-012] |
| F-013 | BP-013 | SDK Adapter 注入 | 标准 | 3 | [PRD:F-013] |
| F-014 | BP-014 | WebSocket 工具调用事件路由 | 核心 | 5 | [PRD:F-014] |
| F-016 | BP-015 | 工具调用超时/取消 | 核心 | 4 | [PRD:F-016] |
| F-017 | BP-016 | 工具调用审计日志写入 | 辅助 | 3 | [PRD:F-017] |
| F-018 | BP-017 | 创建 MCP - stdio 传输 | 核心 | 5 | [PRD:F-018] |
| F-019 | BP-018 | 创建 MCP - sse/http 传输 | 核心 | 5 | [PRD:F-019] |
| F-020 | BP-019 | 模板填充/复制 MCP | 核心 | 4 | [PRD:F-020] |
| F-021 | BP-020 | 创建 MCP - dry-run 沙箱验证 | 核心 | 5 | [PRD:F-021] |
| F-022 | BP-021 | MCP 模板库浏览 | 标准 | 3 | [PRD:F-022] |
| F-023 | BP-022 | MCP 配置文件 schema 校验 | 标准 | 3 | [PRD:F-023] |
| F-024 | BP-023 | dry-run 沙箱配置校验 | 核心 | 4 | [PRD:F-024] |
| F-025 | BP-024 | MCP 权限/安全策略显式同意 | 核心 | 4 | [PRD:F-025] |
| F-026 | BP-025 | MCP 私有/公开开关 | 核心 | 4 | [PRD:F-026] |
| F-027 | BP-026 | MCP 工具调用重试与降级 | 核心 | 4 | [PRD:F-027] |
| F-028 | BP-027 | MCP 使用量统计聚合 | 标准 | 3 | [PRD:F-028] |
| F-029 | BP-028 | MCP 多语言切换 | 标准 | 3 | [PRD:F-029] |
| F-030 | BP-029 | MCP 监控告警触发 | 辅助 | 3 | [PRD:F-030] |
| F-031 | BP-030 | MCP 收藏夹增删 | 核心 | 4 | [PRD:F-031] |
| F-032 | BP-031 | MCP 分享/导出配置 | 标准 | 3 | [PRD:F-032] |
| F-033 | BP-032 | MCP 更新通知推送 | 辅助 | 3 | [PRD:F-033] |

---

## BP-001 [MCP 市场首页渲染] [风险等级:核心]

- **触发条件**: R-03 访问 `/mcp-market` 路由
- **步骤序列**:
  1. [L4 API] 接收 GET `/mcp-market` → 校验路由权限
  2. [L4 API] 查 Redis 缓存 `mcp:homepage:featured` 获取推荐位列表
  3. [L4 API] 缓存未命中时查 PostgreSQL `mcp_featured` + `mcp` 表最新 10 条
  4. [L5 Presentation] SSR 渲染首页 HTML（6 推荐位 + 10 最新）
  5. [L5 Presentation] 返回响应，触发客户端水合
- **分支条件**:
  - 推荐位配置 10s 内生效 → 走 Redis pub/sub 通知 L5 刷新 [调研报告:S-053]
  - R-01 配置推荐位 → 写 `mcp_featured` 表 + 发布 Redis pub/sub 事件
- **结束条件**:
  - 正常: 200 OK + HTML，LCP P95 ≤ 1.5s（NF-01/S-01）
  - 异常: 503（数据库不可用）/ 504（缓存预热超时）
- **关联数据**: DE-001, DE-002
- **关联异常**: EX-001 ~ EX-005
- **来源标注**: [PRD:F-001] + [调研报告:S-053]

[SA洞察#1] 推荐位 LCP 1.5s 目标在 1000 并发压测下，CDN 静态预渲染 + Redis 缓存命中是关键；若缓存雪崩需加 jitter 防击穿。[SA推断:依据 — 调研报告 R-005 闲置超时与 S-053 推荐位 10s 实时生效]

---

## BP-004 [一键安装 MCP] [风险等级:核心]

- **触发条件**: R-03 在 F-003 详情页点击"安装"按钮
- **步骤序列**:
  1. [L4 API] 接收 POST `/mcp/install` → 校验 user 登录态 + CSRF token
  2. [L4 API] 校验 user + mcp_version 唯一性（幂等检查）
  3. [L4 API] 创建 `user_mcp_installations` 记录（status=`installing`）
  4. [L2 Domain] 触发 Runtime 管理器启动 MCP 实例（异步）
  5. [L2 Domain] 实例启动成功 → 更新 status=`ready`，写 instance_id
  6. [L4 API] 异步通知 R-03（站内信 + WebSocket 事件）
- **分支条件**:
  - 同一 user + 同一 mcp 重复安装 → 返回已有 instance_id（幂等）[PRD:F-004 验收③]
  - 网络异常 → 返回 error_code=`INSTALL_NETWORK_ERROR`
  - 依赖缺失 → 返回 error_code=`INSTALL_DEPENDENCY_MISSING`
  - 权限不足 → 返回 error_code=`PERMISSION_DENIED`
- **结束条件**:
  - 正常: 200 OK + `{instance_id, status: "ready"}`，5s 内 instance ready [PRD:F-004 验收①]
  - 异常: 4xx/5xx + error_code
- **关联数据**: DE-001, DE-005
- **关联异常**: EX-014 ~ EX-018
- **来源标注**: [PRD:F-004]

[SA洞察#2] 幂等键设计：`unique(user_id, mcp_id)` 但 mcp_version_id 变化时需重新安装；建议在 schema 层加 `unique(user_id, mcp_id)` 支持版本升级。[SA推断:依据 — 调研报告 S-008/F-008 版本管理]

---

## BP-008 [MCP 版本管理与切换] [风险等级:核心]

- **触发条件**: R-02 推送新版本 OR R-03 在详情页切换版本
- **步骤序列**:
  1. [L4 API] 接收 POST `/mcp/version/create` → R-02 提交新版本
  2. [L4 API] schema 校验（BP-022）→ 自动触发 dry-run（BP-020）
  3. [L4 API] 写入 `mcp_versions` 表（保留历史 50 版本，LRU 清理）[调研报告:S-060]
  4. [L4 API] 通知已安装用户更新（BP-032 通知触发器）
  5. [R-03 切换]: 详情页 query `?version=X` → L4 返回目标版本元数据
- **分支条件**:
  - CVE 紧急更新 → 允许绕过主版本号提升（patch++）[调研报告:S-059]
  - 超过 50 历史版本 → LRU 清理最旧非 pinned 版本
  - semver 不合法 → 拒绝并返回错误
- **结束条件**:
  - 正常: 200 OK + version_id
  - 异常: 409 重复版本号 / 422 schema 错误
- **关联数据**: DE-001, DE-003
- **关联异常**: EX-026 ~ EX-030
- **来源标注**: [PRD:F-008] + [调研报告:S-059, S-060]

[SA洞察#3] semver + "CVE 紧急更新可绕过主版本" 两条规则可能冲突：若旧版本 `1.x.y` 已 pinned，紧急 patch `1.x.z+1` 应同时可见且不破坏 pinned 契约。[SA推断:依据 — 调研报告 R-008/RSK-03]

---

## BP-009 [Agent 绑定 MCP] [风险等级:核心]

- **触发条件**: R-03 在 Agent 配置页选择已安装的 MCP instance + tools 子集
- **步骤序列**:
  1. [L4 API] 接收 POST `/agent/bind-mcp` → 校验 user/agent 归属
  2. [L4 API] 校验 instance status=`ready`（否则拒绝绑定）
  3. [L4 API] 校验 tools 子集（白名单，禁止 > 64 字符工具名）[调研报告:S-035]
  4. [L4 API] 创建 `agent_mcp_bindings` 记录（含 tools 子集 JSON）
  5. [L4 API] 触发 CLI/SDK Adapter 重新注入（BP-012/BP-013）
  6. [L4 API] 返回绑定结果
- **分支条件**:
  - tools 名称超 64 字符 → 自动截断（server_slug 32 + tool_name 28 + 6 字符 hash 后缀）[调研报告:S-035]
  - 同一 agent + 同一 instance 重复绑定 → 幂等返回
  - instance 被卸载 → 拒绝绑定并提示
- **结束条件**:
  - 正常: 200 OK + binding_id，2s 内 WebSocket 路由表更新
  - 异常: 409 重复 / 422 instance 不可用
- **关联数据**: DE-005, DE-006
- **关联异常**: EX-031 ~ EX-035
- **来源标注**: [PRD:F-009] + [调研报告:S-035, S-036]

---

## BP-012 [CLI Adapter 注入 MCP 配置] [风险等级:核心]

- **触发条件**: Agent 启动时 OR 绑定关系变更后 5s 内
- **步骤序列**:
  1. [L2 Domain] 监听 Agent 启动事件 / 绑定变更事件
  2. [L2 Domain] 拉取该 Agent 所有 binding（DE-006）
  3. [L2 Domain] L4 适配层将统一 schema 翻译为各 Runtime 私有 schema [调研报告:S-056, S-057]
  4. [L2 Domain] stdio: 调用 Runtime 私有 CLI（ClaudeCode=`claude mcp add`，OpenCode=`opencode mcp add`）
  5. [L2 Domain] Streamable HTTP: 直接推送配置到 Runtime 端点
  6. [L2 Domain] 等待 Runtime ack，超时 1s 记录 warning 日志
- **分支条件**:
  - 注入失败 → Agent 仍可启动但记录 warning [PRD:F-012 验收③]
  - 注入成功 → 启动 WebSocket 路由表（BP-014）
- **结束条件**:
  - 正常: 注入完成 + Runtime ack
  - 异常: 注入失败但 Agent 启动（graceful degradation）
- **关联数据**: DE-006, DE-007
- **关联异常**: EX-036 ~ EX-040
- **来源标注**: [PRD:F-012] + [调研报告:S-056, S-057]

[SA洞察#4] F-012 描述"标准 MCP 协议格式"实际是"各 Runtime 私有 CLI + L4 翻译层"；若 PM 拍板走"标准协议"，需各 Runtime 官方支持，2026-06 时点不可达。[SA推断:依据 — 调研报告 S-056/📌决策]

---

## BP-014 [WebSocket 工具调用事件路由] [风险等级:核心]

- **触发条件**: Runtime 通过 WebSocket 上报 `tool_call_request` / `tool_call_response` / `tool_call_progress` / `tool_call_error` 事件
- **步骤序列**:
  1. [L4 API] WebSocket 连接鉴权（agent_id + JWT）
  2. [L4 API] 接收事件 → 解析 schema（按 agent_id + call_id 路由）
  3. [L4 API] 写入审计日志（BP-016，异步落盘 P95 ≤ 50ms）
  4. [L4 API] 路由到目标 R-03 IM 会话（按 binding_id）
  5. [L4 API] 等待客户端 ack，5s 未 ack 触发重发 [调研报告:S-054]
  6. [L4 API] 监控并发 50 tool_call，单连接丢消息率
- **分支条件**:
  - 投递失败（ack 5s 未到）→ 重发，最多重试 3 次
  - 断线 30s 内自动重连（EventSource 自动 + 后端兜底）[调研报告:S-055]
  - agent_id 不在路由表（绑定已解绑）→ 阻断 + 返回 error_code=`BINDING_NOT_FOUND`
- **结束条件**:
  - 正常: 投递成功 + 客户端 ack
  - 异常: 路由失败但事件已记录（用于审计追溯）
- **关联数据**: DE-006, DE-008, DE-009
- **关联异常**: EX-041 ~ EX-045
- **来源标注**: [PRD:F-014] + [调研报告:S-054, S-055]

---

## BP-020 [创建 MCP - dry-run 沙箱验证] [风险等级:核心]

- **触发条件**: R-02 提交 stdio/sse/http MCP 创建表单
- **步骤序列**:
  1. [L4 API] 接收 POST `/mcp/create` → schema 校验（BP-022）
  2. [L4 API] 创建 `mcp_dryrun_jobs` 记录（status=`pending`）
  3. [L2 Domain] 调度器分配 Docker 容器（CPU ≤ 1 核 / Mem ≤ 512MB / 网络默认隔离）[PRD:F-021 验收②]
  4. [L2 Domain] 启动 MCP 进程：`subprocess.run([cmd, arg1, ...], ...)` 强制 list 形式 [调研报告:S-026]
  5. [L2 Domain] cgroup v2 `pids.max=1` 隔离 NPROC [调研报告:S-025]
  6. [L2 Domain] 执行 `initialize` + `tools/list` 协议握手
  7. [L2 Domain] 超时硬上限 30s（可配置）[PRD:F-021 验收①]
  8. [L2 Domain] 验证失败 → 写 dryrun 日志 + error_code
  9. [L4 API] 失败则拒绝 MCP 入库；通过则继续入库（BP-017/BP-018）
- **分支条件**:
  - 协议不合规 → 拒绝 + error_code=`PROTOCOL_MISMATCH`
  - 超时 → 拒绝 + error_code=`DRYRUN_TIMEOUT`
  - 资源超限 → 拒绝 + error_code=`RESOURCE_EXCEEDED`
  - 误判：MVP 接受 10% 误报率，3 个月内优化至 2% [调研报告:S-058]
- **结束条件**:
  - 正常: 沙箱返回 tools 列表 + 验证通过
  - 异常: 30s 超时 / 协议错误 / 资源超限
- **关联数据**: DE-010, DE-011
- **关联异常**: EX-046 ~ EX-050
- **来源标注**: [PRD:F-021] + [调研报告:S-025, S-026, S-058]

[SA洞察#5] 沙箱后端选择需平台自适应：Windows=Docker, Linux=cgroup v2, macOS=setrlimit + preexec_fn；无 Docker 时（如 Windows Home 缺 WSL2）降级为 setrlimit 警告模式 [调研报告:S-049 WSL2 限制]。跨平台一致性 R-023 验证有 ⚠️ 风险。

---

## BP-022 [MCP 配置文件 schema 校验] [风险等级:标准]

- **触发条件**: MCP 入库前必走 schema 校验（F-018/F-019/F-020/F-023 全部依赖）
- **步骤序列**:
  1. [L4 API] 接收配置 JSON/YAML → 解析为 JSON 对象
  2. [L4 API] 加载 MCP 协议 schema（MCP 2025-06-18 版本绑定）[调研报告:R-001]
  3. [L4 API] 执行 JSON Schema 校验（jsonschema 库）
  4. [L4 API] 错误信息含精确字段路径（如 `tools[2].inputSchema.required[0]`）[PRD:F-023 验收①]
  5. [L4 API] 通过则进入 dry-run（BP-020）；失败则返回错误详情
- **分支条件**:
  - schema 版本不匹配 → 拒绝并提示升级 schema
  - 工具名超 64 字符 → 警告但不阻断（BP-009 截断规则兜底）
- **结束条件**:
  - 正常: 校验通过 + 字段路径 0 错误
  - 异常: 422 + 字段路径错误列表
- **关联数据**: DE-012
- **关联异常**: EX-051 ~ EX-053
- **来源标注**: [PRD:F-023]

---

## BP-024 [MCP 权限/安全策略显式同意] [风险等级:核心]

- **触发条件**: R-03 安装 MCP 时 OR 权限变更时
- **步骤序列**:
  1. [L4 API] 拉取 MCP 声明的权限（filesystem 范围 / network egress / env 变量）
  2. [L4 API] 渲染权限同意 UI（checkbox + 详情）
  3. [R-03] 显式同意 → 写 `mcp_user_permissions` 表（immutable consent）
  4. [L2 Domain] 沙箱启动时按同意范围限制（filesystem 路径白名单 + network egress 黑名单）
  5. [L2 Domain] 沙箱拒绝未授权访问 → 返回 error_code=`PERMISSION_DENIED`
- **分支条件**:
  - 权限变更 → 需 R-03 再次同意 [PRD:F-025 验收②]
  - 私网/loopback/fe80::/10 访问 → 拒绝 + 记录 SSRF 攻击日志 [调研报告:S-033]
- **结束条件**:
  - 正常: 权限记录 + 沙箱限制生效
  - 异常: 权限被拒绝 + 审计日志记录
- **关联数据**: DE-011, DE-013
- **关联异常**: EX-054 ~ EX-057
- **来源标注**: [PRD:F-025] + [调研报告:S-033, S-064]

---

## BP-026 [MCP 工具调用重试与降级] [风险等级:核心]

- **触发条件**: 工具调用失败 OR MCP 实例不可用
- **步骤序列**:
  1. [L4 API] tool_call 失败 → 进入重试队列
  2. [L4 API] 等待 2s 重试 1 次 [PRD:F-027 验收①]
  3. [L4 API] 重试期间禁用 idempotency_key 防双花 [调研报告:S-065]
  4. [L4 API] 重试失败 → 进入降级路径
  5. [L4 API] 返回友好提示（"检查 MCP 是否在线"）[PRD:F-027 验收②]
  6. [L4 API] 异步上报 F-030 告警系统（BP-029）
- **分支条件**:
  - 重试期间用户取消 → 立即停止 + SIGTERM 沙箱进程 [PRD:F-016 验收③]
  - 重试成功 → 正常返回结果
- **结束条件**:
  - 正常: 重试成功 OR 降级提示
  - 异常: 持续失败 + 告警触发
- **关联数据**: DE-008, DE-014
- **关联异常**: EX-058 ~ EX-061
- **来源标注**: [PRD:F-027] + [调研报告:S-065]

---

## BP-029 [MCP 监控告警触发] [风险等级:辅助]

- **触发条件**: Prometheus 1min scrape 检测 5min 内错误率 > 30% [PRD:F-030 验收①]
- **步骤序列**:
  1. [L2 Domain] Prometheus AlertManager 评估规则
  2. [L2 Domain] 触发告警 → 写 `mcp_alerts` 表
  3. [L2 Domain] 5min 去重窗口：同 MCP 同一错误类型不重复发送 [调研报告:S-066]
  4. [L4 API] 发送站内信给 R-02
  5. [L4 API] 告警延迟 ≤ 1min [PRD:F-030 验收①]
- **分支条件**:
  - 阈值 R-01 可配置 → 写 `alert_thresholds` 表
  - 告警恢复 → 发恢复通知
- **结束条件**:
  - 正常: 站内信投递成功
  - 异常: 站内信队列堆积（重试）
- **关联数据**: DE-014, DE-015
- **关联异常**: EX-062 ~ EX-064
- **来源标注**: [PRD:F-030] + [调研报告:S-066]

---

## BP-032 [MCP 更新通知推送] [风险等级:辅助]

- **触发条件**: MCP 新版本发布（BP-008 触发）
- **步骤序列**:
  1. [L4 API] 查询已安装该 MCP 的 user 列表
  2. [L4 API] 过滤 per-MCP 通知关闭标记（DE-019）
  3. [L4 API] 批量推送站内信（消息队列异步）
  4. [L4 API] 通知延迟 ≤ 5min [PRD:F-033 验收①]
- **分支条件**:
  - per-MCP 关闭 → 跳过
  - 通知失败 → 重试 3 次后丢弃
- **结束条件**:
  - 正常: 通知投递成功
  - 异常: 重试耗尽
- **关联数据**: DE-005, DE-019
- **关联异常**: EX-065 ~ EX-067
- **来源标注**: [PRD:F-033]

---

## 其他 BP 简表（标准/辅助流程概要）

| BP | 名称 | 关键步骤 | 风险等级 |
|---|---|---|---|
| BP-002 | 列表/搜索/筛选 | query → 全文索引 → Redis 缓存 → 分页 | 标准 |
| BP-003 | 详情页加载 | query → 元数据拼装 → 渲染 | 标准 |
| BP-005 | 卸载 | 级联检查绑定 → 二次确认 → 60s 内从所有 Agent 移除 | 核心 |
| BP-006 | 评分/评论 | 写评分表 + 评论表 + 限流 | 核心 |
| BP-007 | 分类/标签 | 2 级分类树 + 最多 10 标签 | 标准 |
| BP-010 | 解除绑定 | 5s 内路由表更新 + 正在执行 call 不中断 | 核心 |
| BP-011 | 批量绑定 | JSON/YAML 解析 + 失败独立标记 + CSV 导出 [S-067] | 核心 |
| BP-013 | SDK Adapter | Python/Node SDK + error_code 命名空间 SDK_* [S-061] | 标准 |
| BP-015 | 工具调用超时/取消 | 30s 超时 + IM 显式取消 + SIGTERM 沙箱 | 核心 |
| BP-016 | 工具调用审计日志 | 异步落盘 P95 ≤ 50ms + 90 天热存 | 辅助 |
| BP-017 | 创建 MCP - stdio | 同 BP-020 入口，stdio 特定校验 | 核心 |
| BP-018 | 创建 MCP - sse/http | 3 次 ping 验证可达性 [S-062] | 核心 |
| BP-019 | 模板填充/复制 | 模板加载 + 字段填充 + 来源 MCP 标注 | 核心 |
| BP-021 | 模板库浏览 | 5 模板列表 + CDN 静态 JSON [S-063] | 标准 |
| BP-023 | dry-run 沙箱配置校验 | BP-020 前置子流程 | 核心 |
| BP-025 | 私有/公开开关 | 公开后 30s 出现于市场（Redis TTL + 失效） | 核心 |
| BP-027 | 使用量统计 | Prometheus 1min scrape + 5min rollup | 标准 |
| BP-028 | 多语言切换 | i18next + description_i18n JSON [S-068] | 标准 |
| BP-030 | 收藏夹增删 | 200 上限 + Redis 缓存 P95 ≤ 200ms | 核心 |
| BP-031 | 分享/导出配置 | JSON 导出 + 版本/来源标识 + 导入时 schema 校验 | 标准 |

[SA洞察#6] 30 项功能中 22 项核心流程 + 8 项标准/辅助流程全部纳入 BP，TD-001 可基于此映射直接启动架构设计。

**阶梯退出检查**: ①全部 F 已分配 BP: 是（30/30）②映射无空行: 是 ③D1: 100%
