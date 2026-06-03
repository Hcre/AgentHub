# PRD 修订建议 — AgentHub MCP 接入 V1.0

> **文档代号**：PRD-REVISION-MCP接入-V1.0-20260602
> **来源调研报告**：RESEARCH-MCP接入-V1.0-20260602.md
> **建议总数**：24 条 S-NNN（与 R-NN 1:1 对应）
> **作者**：RA-001 | **日期**：2026-06-02
> **下游交付**：PM-001 做增量修订（PRD 正文修改权在 PM，RA 不越权）

---

## 修订建议总览

| 编号 | 指向 PRD 条目 | 修订类型 | 优先级 | 决策类型 |
|------|---------------|----------|--------|----------|
| S-001 | F-013/14/15/16 | 表述更新（弃 SSE 用 Streamable HTTP） | 🔴P0 | PM 可直接决定 |
| S-002 | F-014 | 跨平台沙箱方案补全 | 🔴P0 | PM 可直接决定 |
| S-003 | F-015 | 命名 / 库选型更新 | 🔴P0 | PM 可直接决定 |
| S-004 | F-010 | `--mcp-config` 路径 / schema 显式 | 🔴P0 | PM 可直接决定 |
| S-005 | F-011 | 工具命名格式修正（双下划线） | 🔴P0 | PM 可直接决定 |
| S-006 | F-017/018 | 模板版本策略更新 | 🟡P1 | PM 可直接决定 |
| S-007 | F-001/007 | UI 风格参考补充 | 🟡P1 | PM 可直接决定 |
| S-008 | F-006/021 | 进程池选型决策 | 🟡P1 | **📌 PM 需决策** |
| S-009 | F-012, Q-03 | allowlist 决策 | 🟡P1 | **📌 PM 需决策** |
| S-010 | F-014, K4 | 误判率指标调整 | 🟡P1 | PM 可直接决定 |
| S-011 | F-006/021 | 进程池实现路径 | 🟡P1 | **📌 PM 需决策** |
| S-012 | F-002 | manifest 存储技术细节 | 🟡P1 | PM 可直接决定 |
| S-013 | F-022 | 异步写入 / fallback 补全 | 🟢P2 | PM 可直接决定 |
| S-014 | F-010 | 临时文件并发写安全 | 🟡P1 | PM 可直接决定 |
| S-015 | F-025 | 模板版本跟踪机制 | 🟢P2 | PM 可直接决定 |
| S-016 | B-02, Q-10 | Codex/Trae MCP 状态注 | 🔴P0 | PM 可直接决定 |
| S-017 | F-006, F-023 | 崩溃恢复 / 重连细节补全 | 🟡P1 | PM 可直接决定 |
| S-018 | F-012 | 审批超时优化 | 🟡P1 | PM 可直接决定 |
| S-019 | F-007, F-011 | namespace 隔离 / UI 区分 | 🟡P1 | PM 可直接决定 |
| S-020 | F-022, F-025 | token 拦截统一化 | 🟢P2 | PM 可直接决定 |
| S-021 | F-006, K2 | 进程池容量优化 | 🟡P1 | PM 可直接决定 |
| S-022 | F-014 | 网络白名单实现方案 | 🟡P1 | PM 可直接决定 |
| S-023 | F-014 | stderr 截断长度优化 | 🟡P1 | PM 可直接决定 |
| S-024 | F-005, F-018 | 依赖下载 / 离线降级 | 🟢P2 | PM 可直接决定 |

---

## 修订建议详情

### S-001 [P0] MCP 传输表述更新（SSE → Streamable HTTP）

- **指向条目**：PRD F-013 / F-014 / F-015 / F-016
- **问题描述**：PRD 描述三型 transport 为「stdio / SSE / http」，但 MCP 2025-06-18 规范**已将 HTTP+SSE 弃用**（自 2025-03-26 起），新名称为 **Streamable HTTP**（单端点架构）
- **建议改动**：
  - F-013/14/15/16 所有「SSE」字样改为「Streamable HTTP（2025-06-18 规范）」
  - F-013 增加验收「SDK 选型优先 `mcp` Python 包 + `httpx`」
  - F-015 标题改为「提交 streamable_http MCP Server」
- **改动原因**：
  - [来源直接结论] Atlassian Rovo 已设 2026-06-30 弃用日（[MCP spec 报告] 来源 56）
  - [来源直接结论] HTTP+SSE 架构缺陷：双端点、不支持可恢复流、限制水平扩展（[MCP spec 报告] 来源 21、57）
  - [来源直接结论] TypeScript SDK 1.10.0+（2025-04-17）首发支持 Streamable HTTP（[MCP spec 报告] 来源 03）
- **影响评估**：轻度（仅文案与库选型，不影响 F-013/14/15/16 业务逻辑）
- **决策类型**：PM 可直接决定

---

### S-002 [P0] stdio 沙箱跨平台实现补全

- **指向条目**：PRD F-014（dry-run 沙箱）、F-006（进程管理）
- **问题描述**：PRD 假设 `resource.setrlimit` 跨平台可用，但**Windows 不支持** `resource` 模块（Python 官方文档明确），需用 Job Objects (pywin32) 替代
- **建议改动**：
  - F-014 验收标准加「Windows 环境下沙箱用 `pywin32` Job Objects 或 Docker；Linux/macOS 用 `resource.setrlimit` + 平台沙箱 API」
  - 新增验收「跨平台一致性：沙箱在 Windows / macOS / Linux 三平台 CPU/内存限制误差 ≤ 10%」
- **改动原因**：
  - [来源直接结论] Python `resource` 模块不支持 Windows（[Python MCP SDK 报告] 来源 11、50、59）
  - [来源直接结论] RLIMIT_CPU=10s + RLIMIT_AS=512MB 在 Linux 有效防资源耗尽（[Python MCP SDK 报告] 来源 50）
  - [来源直接结论] Docker 沙箱是跨平台一致方案（[Python 沙箱网络报告] 来源 49）
- **影响评估**：中度（增加 Windows 测试矩阵 + 引入 pywin32 依赖）
- **决策类型**：PM 可直接决定

---

### S-003 [P0] sse transport 表述更新（命名 + 库选型）

- **指向条目**：PRD F-015（提交 sse MCP Server）、F-014
- **问题描述**：PRD 假设用 `httpx-sse` 库 + 「sse 沙箱 dry-run」，但 MCP 2025-06-18 后 SSE 已弃用，且官方 Python `mcp` 包提供 `ClientSession` 直接支持 streamable_http
- **建议改动**：
  - F-015 标题改为「提交 streamable_http MCP Server」
  - F-014 沙箱技术选型改用官方 `mcp` Python SDK + `httpx`（不再单独依赖 `httpx-sse`）
- **改动原因**：
  - [来源直接结论] MCP 2025-06-18 后 SSE 已弃用（[MCP spec 报告] 来源 02、22、49）
  - [来源直接结论] `mcp` Python 包提供 ClientSession 支持 stdio/streamable_http（[Python MCP SDK 报告] 来源 04、48、55）
  - [来源直接结论] `httpx-sse` 仍维护但官方推荐直接用 `httpx` 流式响应
- **影响评估**：轻度（库选型优化）
- **决策类型**：PM 可直接决定

---

### S-004 [P0] `--mcp-config` 文件路径与 schema 显式

- **指向条目**：PRD F-010（CLI Adapter 启动时读 bindings 注入 --mcp-config）
- **问题描述**：PRD 描述写到 `/tmp/agenthub/mcp/{agent_id}/{session_id}.json`，但 Claude Code 官方文档长期存在路径错误（指向 `~/.claude/settings.json` 实际无效），正确路径为 `~/.claude.json`（用户级）+ `.mcp.json`（项目级）
- **建议改动**：
  - F-010 临时文件路径从 `/tmp/agenthub/mcp/...` 改为「写到 workspace 临时目录 `workspace_data/mcp/{agent_id}/{session_id}.json`」（避免 /tmp 在容器内丢失）
  - F-010 验收加「文件 schema 根对象 `{mcpServers: {<name>: {command, args, env, type?, timeout?}}}`」
  - F-010 加「3 个 Runtime 需分别实现：ClaudeCode（--mcp-config 注入）、OpenCode（opencode mcp add 子命令 / TOML）、PiAgent（[RA待验证]）」
- **改动原因**：
  - [来源直接结论] Claude Code 官方文档错误指向 `~/.claude/settings.json`，实际是 `~/.claude.json`（[Claude CLI 配置报告] 来源 25、54）
  - [来源直接结论] 项目级配置为 `.mcp.json`（[Claude CLI 配置报告] 来源 24）
  - [来源直接结论] OpenCode MCP 用 TOML 配置 + `opencode mcp add` 子命令（[Codex/Trae 报告] 来源 02、38）
  - [RA推理] PiAgent CLI 当前 MCP 支持情况待 SA-001 二次验证
- **影响评估**：中度（影响 F-010 实现的文件路径与 schema 校验）
- **决策类型**：PM 可直接决定

---

### S-005 [P0] MCP 工具命名格式修正

- **指向条目**：PRD F-011（WebSocket 下行 tool_call/tool_result 事件）
- **问题描述**：PRD 描述「`mcp__` 前缀」单下划线，实测 Claude Code CLI 采用 `mcp__{server_id}__{tool_name}` **双下划线**命名，且受 **OpenAI/Anthropic API 64 字符硬限制**
- **建议改动**：
  - F-011 描述「`mcp__` 前缀」改为「`mcp__{server_id}__{tool_name}` 双下划线命名」
  - F-011 验收加「server_id ≤ 12 字符 + tool_name 总长 ≤ 60 字符（保留 4 字符 buffer）」
  - F-011 新增「超 64 字符时前端告警 + 截断 + 提示重命名」
  - F-011 实现细节加「用 `tool_name.split('__')` 取第 2 段作为 server_id」
- **改动原因**：
  - [来源直接结论] Claude Code 命名格式为 `mcp__{server}__{tool}` 双下划线（[MCP 工具命名报告] 来源 08、23）
  - [来源直接结论] OpenAI/Anthropic API 64 字符硬限制，UUID 长 server_id 直接 400（[MCP 工具命名报告] 来源 03、06、45、54、55）
  - [来源直接结论] 业界建议 server_id 用「UUID 前 8 位 + 短别名」（[MCP 工具命名报告] 来源 03、55、58）
- **影响评估**：中度（影响 F-011 解析逻辑 + 用户 server_id 配置体验）
- **决策类型**：PM 可直接决定

---

### S-006 [P1] 5 模板版本策略更新

- **指向条目**：PRD F-017（5 个内置模板库）、F-018（模板 smoke test 套件）
- **问题描述**：PRD 假设「5 个模板官方 Server 当前可用」，但 MCP 官方 `servers/src/` 仓库已**归档扩展 Server**（GitHub / Brave Search / Postgres / Puppeteer / Slack），核心参考 Server 仅保留 Everything / Fetch / Filesystem / Git / Memory / Sequential Thinking / Time
- **建议改动**：
  - F-017 模板列表更新：
    - filesystem: `@modelcontextprotocol/server-filesystem`（保留）
    - github: `github/github-mcp-server`（官方迁移版本）
    - fetch: `@modelcontextprotocol/server-fetch`（保留）
    - brave-search: `@brave/brave-search-mcp-server`（官方迁移版本）
    - postgres: `crystaldba/postgres-mcp-pro`（社区高级版）
  - F-017 验收加「拉取时校验 + 失败回退到静态 manifest + Inbox 通知」
  - F-018 smoke test 套件加「CVE 已知漏洞回归」（如 Filesystem CVE-2025-53110/53109）
- **改动原因**：
  - [来源直接结论] 官方 `servers/src/` 已归档 GitHub / Brave Search / Postgres（[MCP 官方 Server 报告] 来源 15）
  - [来源直接结论] GitHub MCP Server 迁移到 `github/github-mcp-server`（[MCP 官方 Server 报告] 来源 14、24）
  - [来源直接结论] Filesystem MCP 存在 CVE-2025-53110/53109 目录逃逸（[MCP 官方 Server 报告] 来源 65）
- **影响评估**：中度（影响 F-017 模板表 + F-018 测试矩阵）
- **决策类型**：PM 可直接决定

---

### S-007 [P1] MCP 市场页 UI 风格参考补充

- **指向条目**：PRD F-001（MCP 市场浏览）、F-007（Agent 配置页 MCP 接入 Tab）
- **问题描述**：PRD 未明确 UI 风格参考，业界 5 客户端差异大
- **建议改动**：
  - F-001 验收加「参考 Cline MCP Marketplace UI：卡片网格 + 标签筛选 + 安装数 + 官方/社区徽章」
  - F-007 验收加「绑定交互参考 Continue config.json 模式 + Cline AI 引导」
- **改动原因**：
  - [来源直接结论] Cline 提供 MCP Marketplace + AI 引导安装（[MCP 客户端对比报告] 来源 56）
  - [来源直接结论] Continue 用 config.json + 手动 JSON（[MCP 客户端对比报告] 来源 01）
- **影响评估**：轻度（仅 UI 参考）
- **决策类型**：PM 可直接决定

---

### S-008 [P1] mcp-proxy 选型决策

- **指向条目**：PRD F-006（进程管理）、F-021（健康检查）
- **问题描述**：PRD 未明确 mcp-proxy 选型（自建 vs 依赖 mcp-proxy）
- **建议改动**：
  - 调研倾向：**自建**（Python asyncio + subprocess，与 AgentHub 栈一致）
  - 架构参考：mcp-proxy 的 tower 中间件链（Auth → Audit → Metrics → ... → Circuit Breaker → Outlier Detection）
  - F-006 验收加「中间件风格：Auth / Audit / Metrics / Timeout / Circuit Breaker / Health Check 分层」
  - F-021 加「三层健康检查：Liveness（JSON-RPC ping）/ Readiness（事件循环）/ Functional Status（下游依赖）」
- **改动原因**：
  - [来源直接结论] mcp-proxy 主要为 Rust 实现（awakecoding/sparfenyuk 等），跨语言部署复杂度高（[mcp-proxy 报告] 来源 40、53、54、55）
  - [来源直接结论] mcp-proxy License 为 MIT，可参考架构（[mcp-proxy 报告] 来源 40、53、54、55）
  - [来源直接结论] mcp-proxy 健康检查三层模型（[mcp-proxy 报告] 来源 03、37）
- **影响评估**：重度（影响 F-006/021 实现技术栈）
- **决策类型**：**📌 PM 需决策**（自建 vs 依赖）

---

### S-009 [P1] 危险工具 30 天 allowlist 决策

- **指向条目**：PRD F-012（危险工具走 Inbox 审批）、Q-03（待确认项）
- **问题描述**：Q-03 当前「每次必审批」未拍板；业界 73% 用户偏好 30 天 allowlist（[来源直接结论]）
- **建议改动**：
  - V1 保持「每次必审批」（与 PM 推断一致）
  - P3 backlog（B-10）保留 allowlist 选项
  - F-012 审批超时优化（见 S-018）
- **改动原因**：
  - [来源直接结论] 73% 用户偏好 30 天 allowlist（[MCP 审批报告] 来源 31）
  - [来源直接结论] OWASP MCP Top 10 建议三级风险分级（[MCP 审批报告] 来源 02、07）
  - [PM 推断] 与 SPEC §六「Ask First」一致
- **影响评估**：轻度（V1 不动，仅明确决策）
- **决策类型**：**📌 PM 需决策**（Q-03 拍板）

---

### S-010 [P1] dry-run 误判率指标调整

- **指向条目**：PRD F-014（沙箱 dry-run）、K4（成功指标）
- **问题描述**：PRD K4「沙箱 dry-run 误判率 ≤ 5%」过乐观——前沿 LLM（GPT-5 / Opus 4.5）能以约 1 美元/次成本逃逸容器沙箱
- **建议改动**：
  - K4 改为「沙箱 dry-run 误判率 ≤ 15%」
  - F-014 加验收「灰度发布：先内测 50 个用户提交 case，误判率稳定后再放开」
- **改动原因**：
  - [来源直接结论] 前沿 LLM 能以约 1 美元/次成本逃逸容器沙箱（[Python 沙箱网络报告] 来源 28）
  - [来源直接结论] 容器共享主机内核，runc 连续 CVE（2024-21626、2025-31133、2025-52565、2025-52881）（[Python 沙箱网络报告] 来源 08、28）
- **影响评估**：轻度（仅调整指标）
- **决策类型**：PM 可直接决定

---

### S-011 [P1] 进程池实现路径

- **指向条目**：PRD F-006、F-021
- **问题描述**：与 S-008 关联，重复列出供 PM 决策
- **建议改动**：**📌 PM 需决策** —— 自建 vs 依赖 mcp-proxy（详见 S-008）
- **影响评估**：重度
- **决策类型**：**📌 PM 需决策**

---

### S-012 [P1] manifest 存储技术细节

- **指向条目**：PRD F-002（MCP 列表后端 API）
- **问题描述**：PRD 未明确 manifest 存储技术细节
- **建议改动**：
  - F-002 验收加「用 PG `mcp_servers` 表 + JSONB 列存 manifest 全文 + GIN(jsonb_path_ops) 索引」
  - F-002 验收加「tag 数组列 + GIN 索引」
  - F-004 搜索加「JSONB `@>` 操作符做 tag 包含查询」
- **改动原因**：
  - [来源直接结论] PG JSONB GIN 100 万行包含查询 0.3-0.5ms（[PG JSONB 报告] 来源 18）
  - [来源直接结论] jsonb_path_ops 比 jsonb_ops 小 2-3 倍、速度更快（[PG JSONB 报告] 来源 09、18）
  - [RA推理] AgentHub 现有 PG 栈已含 JSONB 支持
- **影响评估**：轻度（验收标准细化）
- **决策类型**：PM 可直接决定

---

### S-013 [P2] 审计日志异步写入与 fallback

- **指向条目**：PRD F-022（MCP 调用审计日志）
- **问题描述**：PRD 仅说「异步写入」，未提写入失败的 fallback
- **建议改动**：
  - F-022 验收加「asyncio task 异步写入 + 失败 fallback 到本地 `/var/log/agenthub/mcp_call.log`」
  - F-022 验收加「cron 每日 03:00 清理 30 天前日志」
- **改动原因**：
  - [RA推理] 主流程不阻塞（asyncio task）+ 失败本地 disk fallback 防 PG 抖
  - [来源直接结论] GDPR 合规建议 30 天保留（[MCP 审批报告] 来源 44 间接）
- **影响评估**：轻度
- **决策类型**：PM 可直接决定

---

### S-014 [P1] 临时文件并发写安全

- **指向条目**：PRD F-010（CLI 注入）
- **问题描述**：PRD 仅说「60s 滚动 + 进程退出清理」，未提并发写安全
- **建议改动**：
  - F-010 验收加「原子写入：先写 `.tmp` → `os.replace()` 原子重命名」
  - F-010 验收加「flock 文件锁防多进程并发写」
- **改动原因**：
  - [来源直接结论] Claude Code CLI 并发写导致 JSONL 损坏（[Claude CLI 崩溃恢复报告] 来源 41、45）
  - [来源直接结论] 原子写入 + flock 是业界标准（[Claude CLI 崩溃恢复报告] 来源 41）
- **影响评估**：轻度
- **决策类型**：PM 可直接决定

---

### S-015 [P2] 模板版本跟踪机制

- **指向条目**：PRD F-025（MCP 模板版本升级通知）
- **问题描述**：PRD 仅说「CI 每日 03:00 跑 `mcp-template-version-check`」，未明确具体实现
- **建议改动**：
  - F-025 实现细节加「复用 dependabot 模式：拉取上游 release tag diff + SemVer 比较」
  - F-025 验收加「支持 major / minor / patch 分级通知」
- **改动原因**：
  - [RA推理] dependabot / renovate 模式成熟
  - [来源直接结论] MCP 官方 Server release 节奏不规律，平均每周 5.5 commit（[MCP 官方 Server 报告] 来源 17）
- **影响评估**：轻度
- **决策类型**：PM 可直接决定

---

### S-016 [P0] Codex / Trae MCP 状态注

- **指向条目**：PRD B-02（不做项）、Q-10（待确认项）
- **问题描述**：PRD Q-10「Codex/Trae Runtime 规划中无对应文件」未注明实际 MCP 支持状态
- **建议改动**：
  - B-02 加注「Codex CLI 已支持 MCP（2025-04 开源，67K stars；TOML 配置 + stdio/Streamable HTTP）；Trae IDE v1.3.0+ 已支持 MCP（JSON 配置 + 70+ Server 市场）」
  - Q-10 加注「Codex / Trae Runtime 落地后 MCP 适配成本低（Codex 走 TOML 注入；Trae 走 JSON 注入）」
- **改动原因**：
  - [来源直接结论] Codex CLI 已支持 MCP（[Codex/Trae 报告] 来源 24、37）
  - [来源直接结论] Trae IDE v1.3.0+ 支持 MCP（[Codex/Trae 报告] 来源 25、26）
- **影响评估**：轻度（信息补充，不影响接口预留策略）
- **决策类型**：PM 可直接决定

---

### S-017 [P1] 进程崩溃恢复 / WS 重连细节补全

- **指向条目**：PRD F-006（进程管理）、F-023（WS 断线重连）
- **问题描述**：PRD 描述较简略，缺自动 respawn + 崩溃循环检测
- **建议改动**：
  - F-006 验收加「SIGCHLD handler 注册 + 父进程 `waitpid` 防僵尸 + 自动 respawn」
  - F-006 加「崩溃循环检测：同一 server 连续 3 次崩溃后停止 respawn + Inbox 通知」
  - F-023 验收加「WS 断线 30s 内重连：复用同一进程；30s+ 重连：原进程 SIGTERM（5s 宽限）→ SIGKILL，下次启动重 spawn」
- **改动原因**：
  - [来源直接结论] Claude Code CLI 当前实现缺陷：子进程死亡后会话永久损坏（[Claude CLI 崩溃恢复报告] 来源 01）
  - [来源直接结论] WS 重连需要序列号 + ack + 重放（[Claude CLI 崩溃恢复报告] 来源 33、35）
  - [来源直接结论] JSONL transcript 并发写损坏 + 幻影 parentUuid 需原子写入（[Claude CLI 崩溃恢复报告] 来源 36、41）
- **影响评估**：中度（增加实现复杂度）
- **决策类型**：PM 可直接决定

---

### S-018 [P1] 审批超时优化

- **指向条目**：PRD F-012（危险工具审批）
- **问题描述**：PRD F-012「5 min 未审批 → 自动拒绝」偏激进
- **建议改动**：
  - F-012 验收改「10 min 软提醒（Inbox notification） + 30 min 自动拒绝 + 拒绝后允许重提」
  - F-012 加「重提机制：用户主动 click「再试一次」重发审批卡」
- **改动原因**：
  - [来源直接结论] Cloudflare HITL 推荐 4h 提醒 + 24h 升级（[MCP 审批报告] 来源 08）
  - [来源直接结论] Temporal 持久执行支持重提机制（[MCP 审批报告] 来源 22）
  - [RA推理] 5 min 偏激进：用户离开工位即错过
- **影响评估**：轻度
- **决策类型**：PM 可直接决定

---

### S-019 [P1] namespace 隔离 / UI 区分

- **指向条目**：PRD F-007（Agent MCP 接入 Tab）、F-011（WS 事件）
- **问题描述**：PRD 未明确 MCP 工具与域 3 Tool 的 namespace 隔离 + UI 区分
- **建议改动**：
  - F-007 验收加「MCP 工具统一 `mcp__{server}__{tool}` 命名，域 3 工具统一 `domain3__{tool}` 命名」
  - F-011 验收加「前端 ChatView 按 tool_name 前缀渲染不同图标（MCP 显示 server logo，域 3 显示默认工具图标）」
- **改动原因**：
  - [RA推理] 业界无 MCP 客户端实现 namespace 隔离（混用是普遍现象）
  - [来源直接结论] 用前缀区分最简单 + 兼容现有 CLI 流式输出（[MCP 工具命名报告] 来源 08、23）
- **影响评估**：中度（影响 F-007 / F-011 数据模型 + UI）
- **决策类型**：PM 可直接决定

---

### S-020 [P2] token 预算拦截统一化

- **指向条目**：PRD F-022（审计日志）、F-025（模板版本通知 → 关联 settings.coordinator）
- **问题描述**：PRD 未明确 MCP 工具调用是否单独拦截 token 预算
- **建议改动**：
  - F-022 加「token 预算超限拦截统一在 coordinator 层，不区分 MCP / 域 3 工具」
  - F-022 验收加「MCP 工具调用的 input/output token 计入 `usage` 块」
- **改动原因**：
  - [来源直接结论] Claude Code CLI 在 `usage` 块中包含工具调用的 input/output token（[MCP 工具命名报告] 来源 26、29）
  - [RA推理] 区分拦截复杂度高 + 收益低
- **影响评估**：轻度
- **决策类型**：PM 可直接决定

---

### S-021 [P1] 进程池容量优化

- **指向条目**：PRD F-006（进程管理）、K2（成功指标）
- **问题描述**：PRD F-006「单进程池容量 ≥ 32」偏小；K2「≥ 10 MCP/workspace」过保守
- **建议改动**：
  - F-006 验收改「单进程池容量 ≥ 64」
  - K2 保留 ≥ 10（用户视角合理）
  - F-006 加「监控告警：active > 48 时触发 Inbox 通知」
- **改动原因**：
  - [来源直接结论] Linux 64 位 pid_max = 4,194,303（[进程池容量报告] 来源 13）
  - [来源直接结论] systemd TasksMax 默认 ~4477（[进程池容量报告] 来源 04）
  - [RA推理] 满载 10×10 = 100 + 50% 缓冲 ≈ 150 → ulimit 限制下 64 较安全
  - [来源直接结论] Cloudflare MCP 实践 ≤ 64（[进程池容量报告] 来源 60）
- **影响评估**：中度（增加内存占用基线）
- **决策类型**：PM 可直接决定

---

### S-022 [P1] 网络白名单实现方案

- **指向条目**：PRD F-014（沙箱 dry-run）
- **问题描述**：PRD 仅说「仅允许出站到白名单域名（默认全 deny）」，未明确实现
- **建议改动**：
  - F-014 验收加「Docker 优先：`--network=none` + 出口代理（squid / Envoy）」
  - F-014 加「subprocess 降级：Linux 用 network namespace + nftables 出口规则；Windows 用 Hyper-V 虚拟交换机」
  - F-014 加「白名单默认：npm registry (`registry.npmjs.org`) + pypi (`pypi.org`) + 内置 5 模板域名」
- **改动原因**：
  - [来源直接结论] Docker `--network=none` + 出口代理是生产级方案（[Python 沙箱网络报告] 来源 15、17、30）
  - [RA推理] Python `socket.bind` 拦截实现复杂 + 性能损耗 + 可被绕过
- **影响评估**：中度（影响 F-014 实现技术栈）
- **决策类型**：PM 可直接决定

---

### S-023 [P1] stderr 截断长度优化

- **指向条目**：PRD F-014（沙箱 dry-run）
- **问题描述**：PRD 描述「stderr 仅截前 200 字符写入」—— 200 字符可能包含 GitHub PAT（~40 字符）
- **建议改动**：
  - F-014 验收改「stderr 截前 100 字符」
  - F-014 加「secret 字段（`secret: true`）禁止写入 stderr，强制仅走环境变量」
- **改动原因**：
  - [来源直接结论] GitHub PAT 长度 ~40 字符（[MCP 官方 Server 报告] 来源 65）
  - [RA推理] 截 200 字符含 secret 概率 >> 截 100 字符
  - [RA推理] 100 字符足够表达根因（`FileNotFoundError: command not found: ...`）
- **影响评估**：轻度
- **决策类型**：PM 可直接决定

---

### S-024 [P2] 依赖下载 / 离线降级

- **指向条目**：PRD F-005（一键安装）、F-018（smoke test 套件）
- **问题描述**：PRD 未明确 `npx` / `uvx` 首次下载的状态展示 + 离线降级
- **建议改动**：
  - F-005 验收加「首次安装显示「下载中」状态（轮询进度）」
  - F-005 加「离线降级：用户无网络时提示「需手动安装」+ 提供 tarball 链接」
  - F-018 smoke test 加「冷启动 + 首次 npx 下载场景」（CI 镜像预下载依赖）
- **改动原因**：
  - [RA推理] `npx -y` 首次下载 5-30s 取决于网络
  - [RA推理] 离线环境用户需降级方案
- **影响评估**：轻度
- **决策类型**：PM 可直接决定

---

## 修订建议分类汇总

| 类别 | 数量 | 编号 |
|------|------|------|
| 🔴P0（阻塞） | 6 | S-001, S-002, S-003, S-004, S-005, S-016 |
| 🟡P1（重要） | 13 | S-006, S-007, S-008, S-009, S-010, S-011, S-012, S-014, S-017, S-018, S-019, S-021, S-022, S-023 |
| 🟢P2（次要） | 5 | S-013, S-015, S-020, S-024 |
| **📌 需 PM 决策** | 3 | S-008（进程池选型）、S-009（allowlist）、S-011（实现路径） |

> 编号 S-008/S-011 本质同一决策（自建 vs 依赖 mcp-proxy），分两条是为清晰指向不同 PRD 条目。

---

> **版本**：V1.0 | **日期**：2026-06-02 | **作者**：RA-001
> **24 条建议· 6 P0 + 13 P1 + 5 P2 · 3 条需 PM 拍板 · 全部含「改什么→怎么改→为什么」三要素**
