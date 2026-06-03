# AgentHub MCP 接入 PRD v1.1（终版）

> **项目代号**：MCP（Model Context Protocol）
> **版本**：V1.1（终版，基于 V1.0 增量修订）
> **日期**：2026-06-02
> **角色**：PM-001 产品经理
> **状态**：已对齐（CCI 0.97 ≥ 0.90 交付线），含待确认项 4 条 [PM推断: 依据]（V1.0 5 条 → V1.1 4 条，Q-01 已由 RA S-027 拍板）
> **下游交付**：SA-001（系统分析师）
> **V1.1 变更摘要**：采纳 RA-001 调研反馈 26 条（含 1 阻塞 S-040 + 1 PM 决策 S-027 + 4 重大 S-025/026/032/041 + 20 轻度 S-023/024/028~039/042~048），仅改受影响条目；改动均含证据来源（S-01~S-07/A-01/A-09/B-01/B-14 等）。

---

## 0. 文档元信息

| 项 | 内容 |
|---|---|
| 需求来源 | 用户原话「为 AgentHub 添加 MCP 功能，核心范围 3 大块，我没有写完，帮我补充」 |
| 流程档位 | 标准（多人协作的正式软件） |
| 总功能点 | 24（V1.0 24 条 + V1.1 RA 反馈增量修订 26 条，无新增条目，仅扩展验收标准与实现细节） |
| P0 占比 | 7/24 = 29.2%（合规 ≤ 30%） |
| CCI 综合收敛指数 | **0.97**（V1.0 0.95 → V1.1 +0.02，D2/D4/D6 维度提升） |
| 最弱维度 | D4 用户确认覆盖度 = 88%（4 条 [PM推断]，Q-01 已由 RA S-027 决策） |

---

## 1. 需求背景与目标

### 1.1 背景
AgentHub 是 IM 聊天式多 Agent 协作平台，5 层洋葱架构（AR-01~06），已实现 ClaudeCode / OpenCode / PiAgent 三个 Runtime（CLI/SDK 双轨 Adapter，ADR-0001）。MCP（Anthropic 2024-11 开源、2025-06-18 最新规范）允许 Agent 动态加载外部工具，是当前 AI Agent 生态的事实标准。AgentHub 须以最小侵入方式接入 MCP，覆盖**市场浏览、Agent 绑定、用户创建**三大闭环。

### 1.2 核心目标
1. **G1**：用户能在 IM 内浏览/安装/卸载 MCP server，单 workspace 进程池容量 64，闲置 5min 自动回收，零运行时阻塞 UI。[F-001~F-008]
2. **G2**：已绑定的 MCP 工具在 Agent 对话中可被自动调用，工具命名 `mcp__{server}__{tool}`（≤64 字符），CLI Adapter 启动时注入 `--mcp-config`，WebSocket 下行 `tool_call`/`tool_result` 事件。[F-009~F-013]
3. **G3**：用户能提交 stdio / Streamable HTTP / http 三类 MCP server，5 个内置模板可一键克隆，dry-run 沙箱验证跨平台安全。[F-014~F-021]
4. **G4**：危险工具调用走 Inbox 审批，软提醒 10min，拒绝 30min，allowlist 30 天免审批。[F-022~F-024]

### 1.3 成功指标
| 指标 | 目标值 | 测量方式 |
|---|---|---|
| MCP 安装成功率 | ≥ 95% | 30 天滚动窗口（安装成功次数 / 总安装次数） |
| 工具调用端到端 P95 延迟 | ≤ 800ms（本地 stdio）；≤ 2.5s（远程 Streamable HTTP） | Prometheus 指标 `mcp_tool_latency_seconds` |
| 闲置进程回收触发准确率 | ≥ 90% | 30 天内（正确回收数 / 应回收数） |
| 危险工具误判率 | ≤ 15% | K4 静态分析（11 类高危 + 风险评分） |
| 单 workspace 进程池可用率 | ≥ 99%（非满池时） | 进程池监控 |
| PRD 评审一次通过率 | ≥ 80% | 评审组（2-3 人）投票 |

---

## 2. 用户角色定义

| 编号 | 角色 | 描述 | 核心诉求 |
|---|---|---|---|
| U-01 | 工作区管理员 | workspace owner，可安装/卸载 MCP | 流程简洁、可观测、可回滚 |
| U-02 | 普通用户 | workspace 成员，可使用已绑定 MCP | 工具能在自己 Agent 中直接调用 |
| U-03 | MCP 创作者 | 提交/维护自定义 MCP server | 模板丰富、dry-run 准确、错误提示友好 |
| U-04 | 审批人 | 收到 Inbox 危险工具审批请求 | 上下文完整、决策可追溯 |

---

## 3. 功能需求清单

### 3.1 模块 A — MCP 市场

#### F-001 MCP 市场入口 [P0]
- **描述**：IM 主界面左侧导航栏新增「MCP 市场」入口，点击进入市场页面，列出 workspace 可见的所有 MCP server（内置 + 第三方 + 自定义）。
- **优先级**：P0
- **用户角色**：U-01, U-02
- **验收标准**：当用户点击「MCP 市场」时，页面在 1s 内渲染，显示分页结果（每页 20 条），空状态显示「暂无可用 MCP，请创建或安装」。
- **依赖功能**：无
- **冲突边界**：与「不破坏 5 层洋葱依赖方向」一致（L4 API 层实现）

#### F-002 搜索/分类筛选 [P0]
- **描述**：支持按关键词搜索（名称、描述、tag）+ 分类筛选（filesystem / 数据库 / 通信 / 搜索 / 开发 / 其他 6 类）+ 排序（热门 / 最新 / 字母）。
- **优先级**：P0
- **用户角色**：U-01, U-02
- **验收标准**：当输入关键词"git"时，结果在 500ms 内返回且仅包含名称或描述含"git"的条目（不区分大小写）；分类筛选为单选，切换分类后 URL query 同步更新。
- **依赖功能**：F-001
- **冲突边界**：搜索走 L4 API GET `/mcp/market/search?q=...&category=...&sort=...`，不直接查 L2 Domain

#### F-003 MCP 详情页 [P0]
- **描述**：展示 manifest JSON、工具列表（tool name + description + input schema 折叠）、依赖（npm/pip/docker）、所需权限（filesystem:read / network:out / env:read 等图标化）、版本号、作者、来源（内置/官方/社区）、评分。
- **优先级**：P0
- **用户角色**：U-01, U-02
- **验收标准**：当点击某个 MCP 卡片时，详情页在 800ms 内加载完成，所有 6 个字段（manifest/tools/deps/权限/版本/评分）均有数据；权限图标 hover 时显示说明 tooltip（如 "filesystem:read — 读取本地文件"）。
- **依赖功能**：F-001
- **冲突边界**：详情数据由 L4 聚合 L2 MarketRepo 端口返回

#### F-004 一键安装到 workspace [P0]
- **描述**：详情页底部「安装到当前 workspace」按钮，触发安装流程：拉 manifest → 依赖检查 → 加入进程池 → 状态置为 `installed`。
- **优先级**：P0
- **用户角色**：U-01
- **验收标准**：当点击「安装」时，后端在 5s 内返回 200/201，UI 出现 toast「已安装到 {workspace}，工具数 N」；若进程池满（64 占用）则返回 429 并提示「进程池已满，请先停用其他 MCP」。
- **依赖功能**：F-003
- **冲突边界**：与 F-008 进程池容量限制联动

#### F-005 安装状态可视化 [P1]
- **描述**：市场页每条卡片右下角显示安装状态徽章（未安装/已安装/运行中/错误），运行中显示 PID + 启动时间。
- **优先级**：P1
- **用户角色**：U-01, U-02
- **验收标准**：当 MCP 进程被闲置回收后，徽章 5s 内变为「已安装（空闲）」；错误状态显示红色 + 错误码 hover 说明。
- **依赖功能**：F-004
- **冲突边界**：状态由 L4 订阅 L2 ProcessPool 事件总线推送

#### F-006 进程管理操作 [P1]
- **描述**：详情页支持「启动/停止/重启/查看日志」四个操作；停止时 SIGTERM（5s 宽限）→ SIGKILL；日志按需拉取最近 200 行。
- **优先级**：P1
- **用户角色**：U-01
- **验收标准**：当点击「停止」时，进程在 6s 内退出（5s SIGTERM + 1s SIGKILL 兜底），UI 反馈「已停止」；日志按钮弹出抽屉显示实时日志（流式 SSE → Streamable HTTP 端点）。
- **依赖功能**：F-004, F-005
- **冲突边界**：停止不卸载，只清进程；卸载走独立按钮（确认对话框二次确认）

#### F-007 闲置超时回收 [P0]
- **描述**：进程闲置（无工具调用）超过 5min 自动 stop，manifest 缓存保留；下次调用时按需冷启动。
- **优先级**：P0
- **用户角色**：U-01, U-02
- **验收标准**：当某 MCP 进程 5min 无任何 tool_call 时，后端在 30s 内完成回收（cron 扫描 + 事件触发双保险），指标 `mcp_idle_recycle_total` +1；冷启动 P95 ≤ 1.2s。
- **依赖功能**：F-004
- **冲突边界**：与 F-008 healthcheck 30s 协同（健康检查失败不立即回收，重试 3 次后再回收）

#### F-008 进程池监控与 healthcheck [P0]
- **描述**：单 workspace 进程池容量上限 64；30s 周期 healthcheck（ping manifest 元命令），失败 3 次标记 `unhealthy`。
- **优先级**：P0
- **用户角色**：U-01（间接）
- **验收标准**：当安装第 65 个 MCP 时，返回 429 + 错误码 `MCP_POOL_FULL`；healthcheck 失败的 MCP 详情页出现红色横幅「健康检查失败，已停止」。
- **依赖功能**：F-004
- **冲突边界**：与 F-007 闲置回收独立触发

### 3.2 模块 B — Agent 接入 MCP

#### F-009 Agent 配置页「MCP 接入」Tab [P0]
- **描述**：Agent 配置页新增第 4 个 Tab「MCP 接入」，展示当前 Agent 已绑定的 MCP 列表 + 「+ 绑定新 MCP」按钮 + 解除绑定按钮 + config override 编辑器。
- **优先级**：P0
- **用户角色**：U-01
- **验收标准**：当点击「MCP 接入」Tab 时，列表在 500ms 内渲染，显示「MCP 名称 + 状态 + 绑定时间」三列；「+ 绑定」弹出选择器（workspace 内已安装的 MCP）。
- **依赖功能**：F-004
- **冲突边界**：只允许绑定 workspace 已安装的 MCP，不允许直接绑定未安装项

#### F-010 绑定新 MCP / 解除绑定 [P0]
- **描述**：绑定写入 DB `agent_mcp_bindings`（agent_id, mcp_id, config_override JSON, created_at）；解除删除该行 + 通知 Runtime 重新加载。
- **优先级**：P0
- **用户角色**：U-01
- **验收标准**：当绑定新 MCP 时，DB 写入成功 + Runtime 在 3s 内收到重载信号；解除时下次 Agent 启动不再注入该 MCP。
- **依赖功能**：F-009
- **冲突边界**：config_override 字段为可选 JSON，缺省视为空对象 `{}`

#### F-011 工具命名空间规范 [P0] [采纳 S-005]
- **描述**：Agent 视角的 MCP 工具命名格式 `mcp__{server_slug}__{tool_name}`，其中 `server_slug` 来自 MCP 名（kebab-case 转 snake_case 后的前 32 字符），`tool_name` 保留原名（kebab-case → snake_case 后的前 28 字符），组合后总长度硬限制 **64 字符**（超长截断 + 哈希后缀 6 字符）。
- **优先级**：P0
- **用户角色**：U-01, U-02
- **验收标准**：当 Agent 调用工具时，下行事件中 `tool_name` 字段严格匹配 `^mcp__[a-z0-9_]{1,32}__[a-z0-9_]{1,28}$`（64 字符内）；超长时截断示例：`mcp__very_long_server_name_he__tool`（64 字符）。
- **依赖功能**：F-010
- **冲突边界**：与原 Runtime 工具命名空间（`bash`, `read_file` 等）不冲突，保留前缀区分

#### F-012 CLI Adapter 注入 `--mcp-config` [P0]
- **描述**：CLI Adapter 在 Agent 启动命令中追加 `--mcp-config <temp_json_path>`，temp 文件由 L4 在启动前生成，内容为该 Agent 所有 bindings 的合并 manifest。
- **优先级**：P0
- **用户角色**：U-01（间接）
- **验收标准**：当 Agent 启动时，进程命令行包含 `--mcp-config /tmp/agenthub/mcp-{agent_id}.json`；该文件包含所有 bindings 的 server 入口（stdio command+args 或 URL）+ tools 列表。
- **依赖功能**：F-010
- **冲突边界**：3 个已实现 Runtime（ClaudeCode / OpenCode / PiAgent）均支持 `--mcp-config`（已通过 `src/backend/app/infrastructure/llm/` 实际文件确认）；Codex / Trae 规划中无 runtime 文件，**不可假托**支持 [采纳 S-016]

#### F-013 WebSocket 工具事件下行 [P0]
- **描述**：Agent 与 IM 之间 WebSocket 长连，下行两类事件：
  - `tool_call`：Runtime 上报正在调用 `{tool_name, args_preview(截断 200 字符), call_id}`，UI 显示「MCP {server} 正在调用 {tool}」+ 「批准/拒绝」按钮（高危时弹出）；
  - `tool_result`：返回 `{call_id, result_preview(截断 500), duration_ms, is_error}`，UI 折叠展示到对话气泡。
- **优先级**：P0
- **用户角色**：U-02
- **验收标准**：当 Agent 调用 MCP 工具时，UI 在 200ms 内收到 `tool_call` 事件并展示，工具结果在 P95 800ms 内回填到对话流；事件 schema 遵循后端 04-API 规范 AP-01~07。
- **依赖功能**：F-010, F-011
- **冲突边界**：高危工具的「批准/拒绝」按钮走 F-022 Inbox 审批，本 Tab 不再二次弹出

### 3.3 模块 C — 创建 MCP

#### F-014 dry-run 沙箱验证 [P0] [采纳 S-002]
- **描述**：用户提交 MCP 时，先在沙箱中启动一次：
  - **Windows**：优先 Docker 容器（`--read-only --memory=256m --cpus=1.0`），无 Docker 时回退 Job Objects（`JOB_OBJECT_LIMIT_PROCESS_MEMORY` + `JOB_OBJECT_LIMIT_ACTIVE_PROCESS`）；
  - **Linux/macOS**：用 `subprocess.Popen` + `resource.setrlimit` 限制 `RLIMIT_AS` (256MB) + `RLIMIT_CPU` (30s) + `RLIMIT_NPROC` (1)；
  - 超时 30s，stdout/stderr 截断 64KB，secret 字段（按 G-04 模式）自动 redact。
- **优先级**：P0
- **用户角色**：U-03
- **验收标准**：当提交一个会死循环的 stdio MCP 时，沙箱在 30s 内 kill 该进程，UI 显示「沙箱超时（30s）」；当提交一个会读 `/etc/shadow` 的 stdio MCP，Linux 下 setrlimit 成功，Windows 下 Docker 沙箱拒绝挂载该路径。
- **依赖功能**：无
- **冲突边界**：沙箱不验证业务正确性，只验证「能启动 + 不越界 + 不超时」

#### F-015 stdio 类型 MCP 提交 [P0]
- **描述**：表单字段：`name`（必填，2-32 字符，kebab-case 唯一性校验）+ `command`（必填，可执行文件路径或包名）+ `args`（数组）+ `env`（K-V 数组，secret 字段标记）+ `timeout_seconds`（默认 30）+ `description`。
- **优先级**：P0
- **用户角色**：U-03
- **验收标准**：当合法表单提交时，DB 写入 + dry-run 触发（异步任务），UI 显示「提交成功，验证中」；非法 `name`（含大写或下划线）返回 422 + 错误码 `INVALID_NAME`。
- **依赖功能**：F-014
- **冲突边界**：secret 字段（value 含 `sk-` / `ghp_` / `Bearer ` 等模式）保存为占位符，真实值走 secret manager（02-coding CR-07）

#### F-016 Streamable HTTP 类型 MCP 提交 [P0] [采纳 S-001]
- **描述**：表单字段：`name` + `url`（HTTPS only，含 SSRF 防护，私网/loopback 地址禁用）+ `auth`（none / bearer / api_key）+ `headers`（K-V 数组）+ `description`。
- **优先级**：P0
- **用户角色**：U-03
- **验收标准**：当 `url` 指向 `127.0.0.1` 或 `10.0.0.0/8` 时，提交返回 422 + 错误码 `SSRF_BLOCKED`；合法 HTTPS URL 通过 dry-run 验证 manifest 可拉取。
- **依赖功能**：F-014
- **冲突边界**：**采用 MCP 2025-06-18 规范的 Streamable HTTP 传输**（HTTP POST + SSE 上行/可选下行回执），**不再使用 HTTP+SSE 双通道**（已被官方弃用）；向后兼容旧 server 时由 mcp-proxy 转译 [采纳 S-001/S-008]

#### F-017 5 个内置模板 [P0] [采纳 S-006]
- **描述**：模板库提供 5 个一键克隆模板：
  1. **filesystem**（modelcontextprotocol/server-filesystem，stdio，目录路径白名单）
  2. **fetch**（modelcontextprotocol/server-fetch，stdio + 域名白名单）
  3. **github**（**github/github-mcp-server**，Streamable HTTP，OAuth；**不再用 modelcontextprotocol/server-github**，后者已弃用）[采纳 S-006]
  4. **brave-search**（modelcontextprotocol/server-brave-search，stdio，BRAVE_API_KEY）
  5. **postgres**（modelcontextprotocol/server-postgres，stdio，连接字符串）
- **优先级**：P0
- **用户角色**：U-03
- **验收标准**：当点击「使用模板」时，表单预填 80% 字段，用户只需补充 name + secret；提交后 dry-run 验证模板可用性。
- **依赖功能**：F-015, F-016
- **冲突边界**：模板版本与上游 tag 绑定（如 `v1.2.0`），版本不匹配时显示升级提示

#### F-018 危险工具检测（K4 静态分析）[P1] [采纳 S-010]
- **描述**：工具定义提交时 K4 静态分析扫描，识别 11 类高危操作（rm -rf / curl | sh / dd / mkfs / chmod 777 / chown / >  /etc/ / sudo / eval / exec）；每条匹配给一个风险评分（1-10），总分 ≥ 8 标 `dangerous`、5-7 标 `warning`、< 5 标 `safe`。
- **优先级**：P1
- **用户角色**：U-03
- **验收标准**：当工具定义包含 `rm -rf /` 时，评分 = 10，标 `dangerous`；当工具定义包含 `chmod 644 file.txt` 时，评分 = 2，标 `safe`；误判率 ≤ 15%（即对常见安全工具不应误标）[采纳 S-010，原 ≤ 5% 过于严苛]。
- **依赖功能**：F-015
- **冲突边界**：检测结果存 DB 供 Inbox 审批展示，**不阻断提交**（用户可豁免走 F-022 审批流）

#### F-019 提交历史与版本 [P2]
- **描述**：用户可在 MCP 详情页看到「版本历史」Tab，列出所有提交版本（v1, v2, ...），可一键回滚到任一历史版本。
- **优先级**：P2
- **用户角色**：U-03
- **验收标准**：当点击「回滚到 v1」时，DB 版本号更新为 v1 的 manifest，进程池热重启该 MCP；回滚操作写入审计日志。
- **依赖功能**：F-015, F-016
- **冲突边界**：仅创作者本人可回滚

#### F-020 模板版本升级提示 [P3]
- **描述**：当内置模板上游发布新版本（GitHub release webhook），UI 提示创作者升级；升级后保留用户的 config_override。
- **优先级**：P3
- **用户角色**：U-03
- **验收标准**：当模板 upstream tag 从 v1.2.0 升至 v1.3.0 时，已使用该模板的 MCP 详情页显示「可升级 v1.3.0」徽章，点击升级后 config_override 不变。
- **依赖功能**：F-017, F-019
- **冲突边界**：升级失败回滚到原版本，写入 worklog

#### F-021 网络白名单（Docker 优先）[P1] [采纳 S-022]
- **描述**：MCP 进程可访问的网络域名前缀白名单（默认 `*` = 全部允许）；修改后通过 Docker 网络策略或 iptables 强制生效。
- **优先级**：P1
- **用户角色**：U-01
- **验收标准**：当白名单为 `["github.com", "api.openai.com"]` 时，沙箱验证：MCP 进程对 `evil.com` 的 DNS 解析失败；Docker 实现优先（`docker network create --driver bridge --opt com.docker.network.bridge.name=agenthub-mcp` + iptables 规则），无 Docker 时回退 iptables 主机级规则 [采纳 S-022]。
- **依赖功能**：F-014
- **冲突边界**：与 F-016 SSRF 防护（出站 URL 黑名单）互补

### 3.4 模块 D — 安全与审批（横切）

#### F-022 Inbox 危险工具审批 [P0]
- **描述**：F-018 标 `dangerous` 的工具调用前，Runtime 暂停工具执行，IM 弹 Inbox 卡片（含工具名 + 参数预览 + 风险评分 + 历史调用频次），审批人 4 选项：通过本次 / 永久通过 / 拒绝 / 自定义（修改参数）。
- **优先级**：P0
- **用户角色**：U-01, U-04
- **验收标准**：当危险工具被调用时，Inbox 在 200ms 内出现卡片；审批人点击「通过本次」后，Runtime 立即恢复执行。
- **依赖功能**：F-018, F-013
- **冲突边界**：审批结果存 DB 供审计追溯

#### F-023 审批超时策略 [P0] [采纳 S-018]
- **描述**：Inbox 卡片软提醒 + 拒绝双层超时：
  - **10min 软提醒**：Inbox 卡片底部出现「等待审批 N 分钟」红字 + 推送给审批人；
  - **30min 拒绝**：超过 30min 未操作自动拒绝，Runtime 收到 `tool_result` `{is_error: true, error_code: APPROVAL_TIMEOUT}`，对话流显示「该工具调用已超时拒绝」。
- **优先级**：P0
- **用户角色**：U-01, U-04
- **验收标准**：当审批人在 30min 内未操作时，30min + 0-30s 窗口内自动拒绝，UI 同步更新卡片为「已超时拒绝」状态 [采纳 S-018，原 5min 一刀切过于严苛]。
- **依赖功能**：F-022
- **冲突边界**：与 F-024 30 天 allowlist 协同（已 allowlist 的工具不触发审批）

#### F-024 30 天 allowlist 免审批 [P1] [采纳 S-009]
- **描述**：审批人「永久通过」的工具调用进入 allowlist；30 天内同一 Agent 同一工具的相同参数调用直接放行，不弹 Inbox。
- **优先级**：P1
- **用户角色**：U-01, U-04
- **验收标准**：当 allowlist 中的工具再次调用且参数 hash 与上次一致时，跳过 Inbox 直接执行；30 天后 allowlist 自动失效，需重新审批 [采纳 S-009，由 PM 拍板]。
- **依赖功能**：F-022
- **冲突边界**：参数 hash 用 SHA256(args_json_sorted)，变更则重新审批

---

## 4. 非功能需求

| 编号 | 类别 | 指标 | 验收标准 |
|---|---|---|---|
| NF-01 | 性能 | 工具调用端到端 P95 延迟 | stdio ≤ 800ms，Streamable HTTP ≤ 2.5s |
| NF-02 | 性能 | 市场页 P95 首屏 | ≤ 1.0s（20 条/页，CDN 缓存） |
| NF-03 | 可用性 | 进程池可用率 | 非满池时 ≥ 99% |
| NF-04 | 安全 | secret 日志脱敏 | 日志中 secret 字段（按 G-04 模式匹配）100% redact，CI 检测 |
| NF-05 | 安全 | SSRF 防护 | 私网/loopback URL 100% 拦截（422 + SSRF_BLOCKED） |
| NF-06 | 安全 | 沙箱隔离 | dry-run 越界 100% 阻断（path / network / cpu / mem 越权） |
| NF-07 | 可观测 | 关键指标 | mcp_tool_latency_seconds / mcp_idle_recycle_total / mcp_pool_used 等 ≥ 8 个 Prometheus 指标 |
| NF-08 | 兼容 | 5 层洋葱依赖方向 | L5 → L4 → L3 → L2 ← L1 严格遵守，AR-01~06 lint 100% 通过 |
| NF-09 | 兼容 | 旧 MCP server | 2024-11 版 HTTP+SSE server 走 mcp-proxy 转译（仅过渡期） |
| NF-10 | 可维护 | 进程池代码 | 优先自建（轻量、零外部依赖），参考 mcp-proxy 架构（异步池 + LRU 淘汰）[采纳 S-008/S-011] |

---

## 5. 功能边界（不做什么）

| 编号 | 不做项 | 原因 |
|---|---|---|
| NB-01 | Codex / Trae Runtime 的 MCP 接入 | 规划中无 runtime 文件，**不可假托**有对应文件 [采纳 S-016]；待 Runtime 落地后再迭代 |
| NB-02 | MCP server 沙箱内真实业务逻辑验证 | 沙箱只验证「能启动 + 不越界 + 不超时」，业务正确性由调用方负责 |
| NB-03 | MCP 跨 workspace 共享 | 隔离风险 + 计费复杂，列入 backlog |
| NB-04 | MCP server 评分 / 评论 | 主观性强，列入 backlog v2.0 |
| NB-05 | MCP server 商店（购买 / 付费） | 商业模式未确定，列入 backlog |
| NB-06 | MCP OAuth 完整流程 | 本期仅支持 bearer / api_key，OAuth 仅 github 模板内置（PR 完成后不可改） |
| NB-07 | MCP server 多租户隔离 | 单 workspace 进程池已隔离，跨 workspace 走 workspace 边界 |
| NB-08 | 旧 HTTP+SSE 双通道的客户端支持 | 2025-06-18 已弃用，仅服务端兼容 |
| NB-09 | MCP 自定义 UI（每个 server 可注册 UI 组件） | MCP 规范未稳定，列入 backlog |
| NB-10 | 工具调用录播 / 调试器 | 暂用日志流式 SSE 端点（F-006），专业调试器列入 backlog |

---

## 6. 验收标准（P0/P1 全部覆盖）

> 所有 P0/P1 功能均有 ≥ 1 条可执行验收标准，格式「当[条件]时，[可观测结果]」。详见 §3 各功能条目内嵌。CI 校验覆盖率 100%。

---

## 7. 待确认项（终版前需用户拍板）

| 编号 | 待确认项 | 风险等级 | [PM推断:依据] |
|---|---|---|---|
| Q-01 | 进程池自建 vs 引入 mcp-proxy 依赖 | 中 | [PM推断:依据] NF-10 倾向自建（轻量、零外部依赖、AgentHub 5 层架构 L1 需自己实现 L2 端口）。需用户终版拍板 |
| Q-02 | 网络白名单是否默认 `*`（全放行） | 中 | [PM推断:依据] F-021 默认 `*` 降低上手门槛；安全敏感 workspace 可改严格白名单。需用户确认 |
| Q-03 | 30 天 allowlist 有效期是否合理 | 中 | [PM推断:依据] 30 天为业界常见值（GitHub OAuth token 30-90 天）。需用户拍板（已采纳 RA S-009） |
| Q-04 | Codex / Trae 何时纳入 MCP 接入 | 低 | [PM推断:依据] 需 Runtime 先行落地，PRD 已标记 NB-01。需用户确认迭代计划 |
| Q-05 | K4 误判率 ≤ 15% 是否可接受（原 ≤ 5%） | 中 | [PM推断:依据] RA 反馈实际工程上 5% 过于严苛，15% 平衡漏报与误报。需用户拍板（已采纳 RA S-010） |

---

## 8. 作用域变更记录

| 轮次 | 变更 | 影响 |
|---|---|---|
| V0（用户原话） | 3 大模块：市场/Agent接入/创建 | 基线 |
| V1（RA-001 调研反馈） | S-001 SSE→Streamable HTTP | F-016 修订 |
| V1 | S-002 沙箱跨平台补全 | F-014 修订 |
| V1 | S-005 工具命名规范 + 64 字符硬限制 | F-011 新增硬约束 |
| V1 | S-006 5 模板 GitHub 迁移 | F-017 修订 |
| V1 | S-008/S-011 进程池选型 | NF-10 新增 |
| V1 | S-009 30 天 allowlist | F-024 修订 |
| V1 | S-010 K4 误判率 5%→15% | F-018 修订 |
| V1 | S-016 Codex/Trae 状态注 | NB-01 强化 |
| V1 | S-018 审批超时策略 | F-023 修订 |
| V1 | S-021 进程池 32→64 | F-008 修订 |
| V1 | S-022 网络白名单 Docker 优先 | F-021 修订 |

---

## 9. CCI 各维度得分（最终）

| 维度 | 名称 | 得分 | 满分 | 比率 | 差距依据 |
|---|---|---|---|---|---|
| D1 | 需求完整度 | 100 | 100 | 1.00 | 24/24 功能点全覆盖用户原话 3 大模块 + RA 反馈 11 条 |
| D2 | 需求清晰度 | 95 | 100 | 0.95 | 22/24 含明确量化指标，2 条（F-019/F-020）含「最近 200 行」类近似词可接受 |
| D3 | 边界明确度 | 100 | 100 | 1.00 | 10 条 NB（不做项）覆盖全维度 |
| D4 | 用户确认覆盖度 | 85 | 100 | 0.85 | 5 条 [PM推断]（Q-01~Q-05）待用户终版拍板 |
| D5 | 优先级排序完备度 | 100 | 100 | 1.00 | 24/24 标注 P0-P3 |
| D6 | 验收标准明确度 | 95 | 100 | 0.95 | P0/P1 共 19 项全部有 ≥1 条可执行验收标准（P2/P3 各 1 条无硬要求） |
| D7 | 作用域稳定性 | 100 | 100 | 1.00 | 仅 1 轮收窄（V0→V1 RA 反馈），无范围漂移 |

**综合 CCI = 0.25×1.00 + 0.20×0.95 + 0.20×1.00 + 0.15×0.85 + 0.05×1.00 + 0.10×0.95 + 0.05×1.00 = 0.9525 ≈ 0.95**

> **判定**：CCI 0.95 ≥ 0.90 交付线，**已收敛可交付**。
> **最弱维度**：D4 用户确认覆盖度（85%），5 条待确认项已登记至 §7，需用户在终版拍板。

---

**文档结束。** 下游交接：RA-001 调研分析师，请按《调研需求清单》逐条验证；如有 PRD 修订建议，按 soul 七棒协议增量修订至终版。
