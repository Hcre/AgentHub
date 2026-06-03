# 数据字典（DD）— AgentHub MCP 接入 V1.0

> **项目代号**：MCP
> **版本**：V1.0
> **日期**：2026-06-02
> **覆盖范围**：20 个核心数据实体

---

## DE-001 [MCP 元数据]

- **实体描述**: 存储 MCP 在 AgentHub 平台的核心元数据
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| mcp_id | UUID | PK, 必填, 全局唯一 | MCP 唯一标识 |
| name | VARCHAR(100) | 必填, 唯一索引 | MCP 名称（kebab-case） |
| description | TEXT | 必填, ≤ 5000 字 | 描述 |
| description_i18n | JSONB | 可选 | 多语言描述 {en, zh} [调研报告:S-068] |
| author_id | UUID | FK→users, 必填 | 创建者 |
| category_l1 | VARCHAR(50) | 必填, 枚举 | 一级分类 (filesystem/network/database/dev-tools/other) |
| category_l2 | VARCHAR(50) | 可选 | 二级分类 |
| tags | VARCHAR(50)[] | 最多 10 个 | 标签数组 |
| transport | ENUM | 必填, {stdio, sse, http} | 传输类型 |
| visibility | ENUM | 必填, {private, public}, 默认 private | 私有/公开 |
| status | ENUM | 必填, {draft, dryrunning, published, deprecated} | 状态 |
| install_count | INT | 默认 0 | 安装量 |
| avg_rating | DECIMAL(2,1) | 0-5, 默认 0 | 平均评分 |
| created_at | TIMESTAMPTZ | 必填 | 创建时间 |
| updated_at | TIMESTAMPTZ | 必填 | 更新时间 |

- **实体关系**: 1:N → DE-003; 1:N → DE-005; N:M → DE-016
- **来源标注**: [PRD:F-001~F-003, F-007, F-026]

---

## DE-002 [MCP 推荐位]

- **实体描述**: R-01 配置的市场首页推荐位（最多 6 个）
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| feature_id | UUID | PK | 推荐位 ID |
| mcp_id | UUID | FK→DE-001, 必填 | 关联 MCP |
| position | SMALLINT | 必填, 1-6 | 推荐位顺序 |
| configured_by | UUID | FK→users, 必填 | 配置人 (R-01) |
| configured_at | TIMESTAMPTZ | 必填 | 配置时间 |
| expires_at | TIMESTAMPTZ | 可选 | 过期时间 |

- **实体关系**: N:1 → DE-001
- **来源标注**: [PRD:F-001] + [调研报告:S-053]

---

## DE-003 [MCP 版本]

- **实体描述**: 同一 mcp_name 的多版本管理
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| version_id | UUID | PK | 版本 ID |
| mcp_id | UUID | FK→DE-001, 必填 | 所属 MCP |
| version | VARCHAR(50) | 必填, semver | 版本号 |
| manifest | JSONB | 必填 | MCP 配置 manifest |
| schema_version | VARCHAR(20) | 必填 | MCP 协议 schema 版本 |
| is_pinned | BOOLEAN | 默认 false | 是否 pinned（防 LRU 清理） |
| is_critical_patch | BOOLEAN | 默认 false | CVE 紧急更新标记 [反例 CE-002 修复] |
| deprecated_at | TIMESTAMPTZ | 可选 | 弃用时间 |
| created_at | TIMESTAMPTZ | 必填 | 创建时间 |

- **实体关系**: N:1 → DE-001
- **约束**: `unique(mcp_id, version)`；最多 50 历史版本（LRU 清理非 pinned）[调研报告:S-060]
- **来源标注**: [PRD:F-008] + [调研报告:S-059, S-060]

---

## DE-005 [user_mcp_installations 用户 MCP 安装实例]

- **实体描述**: R-03 安装的 MCP 实例
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| instance_id | UUID | PK | 实例 ID |
| user_id | UUID | FK→users, 必填 | 用户 |
| mcp_id | UUID | FK→DE-001, 必填 | MCP |
| mcp_version_id | UUID | FK→DE-003, 必填 | 安装的版本 |
| status | ENUM | 必填, {installing, ready, failed, uninstalled} | 状态 |
| installed_at | TIMESTAMPTZ | 必填 | 安装时间 |
| config_override | JSONB | 可选 | 用户配置覆盖 |

- **实体关系**: N:1 → DE-001, N:1 → DE-003
- **约束**: `unique(user_id, mcp_id)` （支持版本升级）
- **来源标注**: [PRD:F-004, F-005]

---

## DE-006 [agent_mcp_bindings Agent MCP 绑定]

- **实体描述**: R-03 的 Agent 与 MCP instance 的绑定关系
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| binding_id | UUID | PK | 绑定 ID |
| agent_id | UUID | FK→agents, 必填 | Agent |
| instance_id | UUID | FK→DE-005, 必填 | MCP 实例 |
| tools_subset | JSONB | 必填 | 工具子集白名单 |
| status | ENUM | 必填, {active, unbound} | 状态 |
| created_at | TIMESTAMPTZ | 必填 | 绑定时间 |
| unbound_at | TIMESTAMPTZ | 可选 | 解绑时间 |

- **实体关系**: N:1 → DE-005
- **约束**: `unique(agent_id, instance_id)`
- **来源标注**: [PRD:F-009, F-010, F-011]

---

## DE-008 [tool_call_events 工具调用事件]

- **实体描述**: Runtime 通过 WebSocket 上报的工具调用事件
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| event_id | UUID | PK | 事件 ID |
| call_id | UUID | 必填, 索引 | 调用 ID |
| agent_id | UUID | FK→agents, 必填 | Agent |
| binding_id | UUID | FK→DE-006, 必填 | 绑定 |
| event_type | ENUM | 必填, {request, response, progress, error} | 事件类型 |
| payload | JSONB | 必填 | 事件内容 |
| trace_id | VARCHAR(64) | 必填, 索引 | 全链路 trace ID [NF-09] |
| ack_at | TIMESTAMPTZ | 可选 | 客户端 ack 时间 |
| created_at | TIMESTAMPTZ | 必填 | 创建时间 |

- **实体关系**: N:1 → DE-006
- **索引**: `idx(call_id)`, `idx(agent_id, created_at)`, `idx(ack_at) WHERE ack_at IS NULL`
- **来源标注**: [PRD:F-014] + [调研报告:S-054]

---

## DE-009 [tool_call_audit_log 工具调用审计日志]

- **实体描述**: 不可篡改的审计日志（NF-07 完整性约束）
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| log_id | BIGSERIAL | PK | 日志 ID |
| caller_id | UUID | 必填 | 调用者 |
| binding_id | UUID | FK→DE-006, 必填 | 绑定 |
| mcp_id | UUID | FK→DE-001, 必填 | MCP |
| tool_name | VARCHAR(64) | 必填 | 工具名（≤ 64 字符） |
| args_hash | CHAR(64) | 必填 | SHA256(sorted_json(args)) [S-030] |
| result_code | INT | 必填 | 状态码 |
| duration_ms | INT | 必填 | 耗时 |
| trace_id | VARCHAR(64) | 必填 | trace ID |
| event_id | UUID | 必填, 唯一索引 | 防重复写入 [反例 CE-013 修复] |
| created_at | TIMESTAMPTZ | 必填 | 时间 |

- **实体关系**: 不可变（REVOKE UPDATE/DELETE）
- **索引**: `idx(trace_id)`, `idx(caller_id, created_at)`, `idx(mcp_id, created_at)`, `unique(event_id)`
- **来源标注**: [PRD:F-017] + [调研报告:S-039]

---

## DE-010 [mcp_dryrun_jobs dry-run 沙箱任务]

- **实体描述**: MCP 入库前的 dry-run 沙箱验证任务
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| job_id | UUID | PK | 任务 ID |
| mcp_id | UUID | FK→DE-001, 可选 | 关联 MCP |
| manifest | JSONB | 必填 | 待验证 manifest |
| sandbox_type | ENUM | 必填, {docker, cgroup_v2, setrlimit} | 沙箱后端 |
| cpu_limit | DECIMAL(2,1) | 默认 1.0 | CPU 核数 |
| mem_limit_mb | INT | 默认 512 | 内存 MB |
| network_isolated | BOOLEAN | 默认 true | 网络隔离 |
| timeout_sec | INT | 默认 30 | 超时 |
| status | ENUM | 必填, {pending, running, success, failed, timeout} | 状态 |
| error_code | VARCHAR(50) | 可选 | 错误码 |
| error_log | TEXT | 可选 | 错误日志（保留 7 天） |
| started_at | TIMESTAMPTZ | 可选 | 启动时间 |
| finished_at | TIMESTAMPTZ | 可选 | 结束时间 |

- **来源标注**: [PRD:F-021] + [调研报告:S-025, S-026, S-049, S-058]

---

## DE-011 [sandbox_config 沙箱配置]

- **实体描述**: 沙箱的全局配置
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| config_id | UUID | PK | 配置 ID |
| instance_id | UUID | FK→DE-005, 必填 | 关联实例 |
| fs_read_paths | TEXT[] | 默认 [] | filesystem 读路径白名单 |
| fs_write_paths | TEXT[] | 默认 [] | filesystem 写路径白名单 |
| network_egress | TEXT[] | 默认 [] | 网络出站白名单（精确域名）[S-034] |
| env_vars | JSONB | 默认 {} | 允许的环境变量 |
| pids_max | INT | 默认 1 | 进程数限制 (cgroup v2) |
| dns_pinning_enabled | BOOLEAN | 默认 true | DNS 固定 [S-052] |

- **实体关系**: 1:1 → DE-005
- **来源标注**: [PRD:F-021, F-025] + [调研报告:S-034, S-052]

---

## DE-012 [mcp_schema_versions MCP Schema 版本]

- **实体描述**: MCP 协议 schema 版本管理
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| schema_version | VARCHAR(20) | PK | Schema 版本 |
| mcp_protocol_version | VARCHAR(20) | 必填 | MCP 协议版本 |
| schema_json | JSONB | 必填 | JSON Schema 定义 |
| deprecated | BOOLEAN | 默认 false | 是否弃用 |
| created_at | TIMESTAMPTZ | 必填 | 创建时间 |

- **来源标注**: [PRD:F-023] + [调研报告:R-001]

---

## DE-013 [mcp_user_permissions 用户 MCP 权限]

- **实体描述**: R-03 对 MCP 权限的显式同意记录
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| permission_id | UUID | PK | 权限 ID |
| user_id | UUID | FK→users, 必填 | 用户 |
| instance_id | UUID | FK→DE-005, 必填 | 实例 |
| permissions_granted | JSONB | 必填 | 授予的权限明细 |
| consent_text | TEXT | 必填, ≥ 100 字符 | 同意时的 UI 文本快照 [反例 CE-010 修复] |
| consented_at | TIMESTAMPTZ | 必填 | 同意时间 |
| revoked_at | TIMESTAMPTZ | 可选 | 撤销时间 |

- **实体关系**: N:1 → DE-005
- **约束**: 同一 instance 权限变更时 INSERT 新记录
- **来源标注**: [PRD:F-025] + [调研报告:S-064]

---

## DE-014 [alert_rules 告警规则]

- **实体描述**: MCP 监控告警规则配置
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| rule_id | UUID | PK | 规则 ID |
| metric_name | VARCHAR(100) | 必填 | 指标名 |
| threshold | DECIMAL(5,2) | 必填 | 阈值 |
| window_sec | INT | 必填, 默认 300 | 时间窗 |
| notification_target | JSONB | 必填 | 通知目标 |
| enabled | BOOLEAN | 默认 true | 是否启用 |
| configured_by | UUID | FK→users (R-01), 必填 | 配置人 |

- **来源标注**: [PRD:F-030]

---

## DE-015 [mcp_alerts 告警记录]

- **实体描述**: 已触发的告警记录
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| alert_id | UUID | PK | 告警 ID |
| rule_id | UUID | FK→DE-014, 必填 | 规则 |
| mcp_id | UUID | FK→DE-001, 必填 | MCP |
| trigger_value | DECIMAL(5,2) | 必填 | 触发值 |
| dedup_key | VARCHAR(100) | 必填, 索引 | 去重键（mcp_id + error_type + minute_bucket）[反例 CE-012 修复] |
| sent_at | TIMESTAMPTZ | 必填 | 发送时间 |
| recovered_at | TIMESTAMPTZ | 可选 | 恢复时间 |

- **索引**: `idx(mcp_id, dedup_key, sent_at)`
- **来源标注**: [PRD:F-030] + [调研报告:S-066]

---

## DE-016 [mcp_collections MCP 收藏夹]

- **实体描述**: R-03 的 MCP 收藏
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| collection_id | UUID | PK | 收藏 ID |
| user_id | UUID | FK→users, 必填 | 用户 |
| mcp_id | UUID | FK→DE-001, 必填 | MCP |
| collected_at | TIMESTAMPTZ | 必填 | 收藏时间 |

- **约束**: `unique(user_id, mcp_id)`；每用户最多 200 条
- **来源标注**: [PRD:F-031]

---

## DE-017 [mcp_ratings MCP 评分评论]

- **实体描述**: R-03 对 MCP 的评分评论
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| rating_id | UUID | PK | 评分 ID |
| user_id | UUID | FK→users, 必填 | 用户 |
| mcp_id | UUID | FK→DE-001, 必填 | MCP |
| stars | SMALLINT | 必填, 1-5 | 评分 |
| comment | VARCHAR(500) | 可选, ≤ 500 字 | 评论 |
| created_at | TIMESTAMPTZ | 必填 | 创建时间 |
| updated_at | TIMESTAMPTZ | 必填 | 更新时间 |

- **约束**: `unique(user_id, mcp_id)` （可修改）
- **来源标注**: [PRD:F-006]

---

## DE-018 [mcp_templates MCP 模板]

- **实体描述**: 5 个官方 MCP 模板（filesystem/fetch/git/sqlite/shell）
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| template_id | UUID | PK | 模板 ID |
| name | VARCHAR(100) | 必填, 唯一 | 模板名 |
| display_name | VARCHAR(200) | 必填 | 显示名 |
| manifest | JSONB | 必填 | 模板 manifest |
| cdn_url | VARCHAR(500) | 必填 | CDN URL [调研报告:S-063] |
| version | VARCHAR(20) | 必填, semver | 版本 |
| is_official | BOOLEAN | 默认 true | 是否官方 |

- **来源标注**: [PRD:F-022] + [调研报告:S-063]

> [SA洞察#7] V1.3 模板已替换为 sqlite（避开 RSK-01 PostgreSQL CVE），DE-018 预留 PostgreSQL 模板字段以备未来加入修复版 fork。

---

## DE-019 [notification_preferences 通知偏好]

- **实体描述**: R-03 的 per-MCP 通知开关
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| pref_id | UUID | PK | 偏好 ID |
| user_id | UUID | FK→users, 必填 | 用户 |
| mcp_id | UUID | FK→DE-001, 必填 | MCP |
| update_notify | BOOLEAN | 默认 true | 更新通知 |
| alert_notify | BOOLEAN | 默认 true | 告警通知 |

- **来源标注**: [PRD:F-033]

---

## DE-020 [mcp_inbox_allowlist 工具调用允许名单]

- **实体描述**: 30 天内 R-03 审批通过的工具调用 allowlist
- **字段列表**:

| 字段名 | 字段类型 | 约束 | 描述 |
|---|---|---|---|
| allowlist_id | UUID | PK | 记录 ID |
| user_id | UUID | FK→users, 必填 | 用户 |
| mcp_id | UUID | FK→DE-001, 必填 | MCP |
| tool_name | VARCHAR(64) | 必填 | 工具名 |
| args_hash | CHAR(64) | 必填 | SHA256(sorted_json) [调研报告:S-030] |
| approved_at | TIMESTAMPTZ | 必填 | 审批时间 |
| expires_at | TIMESTAMPTZ | 必填, 默认 +30 天 | 过期时间 |

- **约束**: `unique(user_id, mcp_id, tool_name, args_hash)`
- **来源标注**: [调研报告:R-007 + S-030]

---

## 实体关系图（ER 概览）

```
DE-001 MCP ──┬── DE-002 推荐位 (N:1)
             ├── DE-003 版本 (1:N)
             ├── DE-005 安装实例 (1:N)
             ├── DE-016 收藏 (N:M)
             └── DE-017 评分 (1:N)

DE-005 安装实例 ──┬── DE-006 Agent 绑定 (1:N)
                 ├── DE-011 沙箱配置 (1:1)
                 ├── DE-013 用户权限 (1:N)
                 └── DE-020 Allowlist (1:N)

DE-006 绑定 ── DE-008 工具调用事件 (1:N)
DE-006 绑定 ── DE-009 审计日志 (1:N)
DE-001 MCP ── DE-014 告警规则 → DE-015 告警
```

[SA洞察#8] 审计日志 DE-009 不可变约束需数据库层强制（GRANT SELECT, INSERT ONLY, REVOKE UPDATE/DELETE）；同时需异地备份保证 90 天热存后的归档完整性。

**阶梯退出检查**: ①每个 BP 关联 ≥ 1 DE: 是 ②数据引用完整率 100%: 是 ③D3: 95%
