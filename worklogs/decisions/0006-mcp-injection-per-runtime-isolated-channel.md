# ADR-06：MCP 注入的统一原则 = 每 Runtime 经「逐调用隔离通道」翻译注入

> 日期：2026-06-04 | 状态：**Accepted** | 决策人：袁（Claude Agent 协助）
> 关联：[ADR-05](0005-mcp-attach-request-carried.md)（请求携带）· `docs/specs/01-architecture` §MCP.2 · README-REVISION §9 R11
> 性质：对 R11/ADR-05「MCP 注入 claude_code-only，opencode/pi_agent 移 NB-02」的**校正与细化**（docs-only 冻结，代码下一会话落地）

## 一、背景

ADR-05 把 MCP 注入定为**请求携带**（`AgentRequest.mcp_servers`，运行时无状态），并接通了 claude_code（`--mcp-config <tempfile>`）。随后的运行时审计（R11）把 opencode/pi_agent 移到 NB-02，理由是「未验证 / opencode 写全局会串号 / pi 无 MCP flag」。

本会话按项目「方法固化」红线（*凡「N 个组件都能做 X」的断言，必须逐个打开验证 X 在每个组件里可行*）**逐个实测**，发现 R11 的判断对 opencode 部分过时：

| CLI | 本机验证（2026-06-04） | 结论 |
|-----|----------------------|------|
| claude_code | 已实现，`--mcp-config <tempfile>` 逐调用注入 | 已通 |
| **opencode** | v1.15.10 已装；`opencode mcp` 子命令存在；**实测 `OPENCODE_CONFIG=<tmp> opencode mcp list` 注入成功**（探针出现 / control 为空）。配置精度为逐进程 env，非全局 | **有逐调用隔离通道**，可拉回本期 |
| pi_agent | 本机无 `pi` 二进制、无可查源码（helio-desktop 为无关 Electron 应用）；CLI 无确认 MCP flag | **不可运行验证** → 保持 deferred |

关键发现：opencode 的 `OPENCODE_CONFIG` 环境变量 = claude_code `--mcp-config` 的等价物——逐进程指向临时配置文件，**根本不需要碰全局 `~/.config/opencode/opencode.jsonc`**，故 R11 的「写全局串号」根因不成立。

## 二、决策

### 1. 统一原则（本 ADR 核心，跨全部 CLI 冻结）

> **每个 Runtime 把 `request.mcp_servers`（ADR-05 请求携带的 canonical 条目）翻译成该 CLI 的原生 MCP schema，经该 CLI「隔离性最强的逐调用通道」注入；永不改全局/共享配置。没有逐调用通道的 CLI 保持 deferred，直到上游提供。**

隔离通道优先级（择强者用）：

| 优先级 | 通道 | 示例 |
|-------|------|------|
| 1 | 逐调用 flag | claude_code `--mcp-config <tmp>` |
| 2 | env 指向临时配置文件 | opencode `OPENCODE_CONFIG=<tmp>` |
| 3 | 逐 workspace 项目配置文件 | （仅当 1/2 不可用，且需保证非共享 cwd） |
| ❌ | 全局/共享配置 mutation | 跨 agent 串号，**禁止** |

此原则与 ADR-05 选「请求携带」同源：逐调用通道天然零串号，连群聊里**同 workspace 的多 agent** 也不混（每次 spawn 独立 env/flag）。

### 2. opencode：拉回本期（NB-02 → 本期）

- 翻译层 `_entry_to_opencode()`（放 `opencode_runtime.py`，对齐 claude_code 的 `_entry_to_claude` 位置）。字段差异：

  | canonical（`build_mcp_config_entry`） | opencode |
  |---|---|
  | `{type:"stdio", command:"x", args:[...], env:{}}` | `{type:"local", command:["x", ...args], environment:{}, enabled:true}` |
  | `{type:"sse"\|"http", url, headers}` | `{type:"remote", url, headers, enabled:true}` |

  注意：opencode `command` 是**数组**（命令+参数合并）、env 键为 `environment`、需 `enabled:true`。

- 注入：每次 `stream()` 写**自包含**临时配置（provider 块 + `mcp` 块都在内，规避 `OPENCODE_CONFIG` merge/replace 语义歧义），`env["OPENCODE_CONFIG"]=tmp`，atexit 清理。
- opencode runtime 每次 `stream()` spawn 新进程（非长驻池化）→ **无需** claude_code 那套「配置变化重 spawn 守卫」，实现更简单。
- 顺手补齐：把董的 `agenthub-memory`（SSE）作为 `remote` 条目注入 → 修复 R11 指出的「连记忆 MCP 也只 claude_code 生效」。
- 测试（T-05 必测）：`_entry_to_opencode` 三形态（stdio/remote/env）单测 + 配置写入断言；可选 `OPENCODE_CONFIG + opencode mcp list` 冒烟。

### 3. pi_agent：受控 seam，不落可执行代码

本机不可运行、源码不可查、无确认 MCP flag。按「可观测验证」红线与 T-05（Adapter 必测），**不写无法运行验证的 adapter 代码**。处置：

- 在 `pi_agent_runtime._build_cmd` 留明确注入点 + `# NB-02: blocked on upstream pi CLI MCP support（见 ADR-06 §2.3）` 注释。
- 验证 checklist（解除 deferred 的前置门）：① 确认 pi CLI 是否有 MCP config / extension API；② 有 → 按统一原则找逐调用通道接入 + 实测；③ 无 → 上游提 issue，保持 deferred。

### 4. 后续 CLI（codex / gemini，均未实现）

套用统一原则，不在本 ADR 展开：
- codex：`~/.codex/config.toml` `[mcp_servers]`，逐调用通道 = `CODEX_HOME` 指向临时目录 或 `-c` override。
- gemini：`~/.gemini/settings.json` `mcpServers`，逐调用通道 = 项目 `.gemini/settings.json` 或 env。

接入新 CLI 时：找逐调用通道 → 写翻译函数 → 禁止改全局。

## 三、影响 / 后续

- 不动数据模型 / API 端点（请求携带链路 P2 已通）→ **不触发 PR-01**。
- spec 同步（PR-09）：`01-architecture §MCP.2` 已改（opencode 拉回本期、统一原则、pi seam）。README-REVISION §9 R11 与 roadmap §十 P2 行同步备注本 ADR。
- 本 ADR 为 docs-only 冻结；opencode 代码 + 测试在下一会话按本方案落地。
- 单一权威入口仍为 README-REVISION；本 ADR 是其 §9 R11 的细化决策记录。
