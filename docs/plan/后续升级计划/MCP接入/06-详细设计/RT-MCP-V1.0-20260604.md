# RT-MCP — MCP Runtime 注入接入计划（opencode 拉回 + pi seam + 后续 CLI）

> 版本：V1.0-20260604 · 作者：袁（Claude Agent 协助）
> 权威依据：[ADR-06](../../../../../worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md)（统一注入原则）· [ADR-05](../../../../../worklogs/decisions/0005-mcp-attach-request-carried.md)（请求携带）
> 单一权威入口：[README-REVISION.md](../README-REVISION.md) §9 R11
> 性质：本文件是 ADR-06 的**落地施工蓝图**（下一会话执行）。docs-only，未动代码。

---

## 0. 一句话

把 ADR-05 已通的「请求携带」链路，从 claude_code-only 扩展到 **opencode**（本期拉回，可测）；**pi_agent** 留受控 seam（deferred）；后续 CLI 给统一接法。

---

## 1. 不变量（接入任何 CLI 都成立）

| 不变量 | 出处 | 说明 |
|--------|------|------|
| 请求携带，运行时无状态 | ADR-05 | `AgentRequest.mcp_servers: list[dict]` 已是唯一入口；Runtime 不持 binding 状态 |
| canonical 条目格式 | `domain/mcp/rules.py::build_mcp_config_entry` | stdio `{name,type:"stdio",command,args?,env?}` / 远程 `{name,type:"http"\|"sse",url,headers?}` |
| 逐调用隔离通道 | ADR-06 | flag > env→临时文件 > 逐 workspace 项目配置 > ❌ 全局 mutation |
| 解析侧零改动 | 现状 | `_parse_line` 已透传 tool_call/tool_result；MCP 工具的 server 来源标注属 P4，不在本计划 |

**翻译职责**：每个 Runtime 自带一个纯函数，把 canonical 条目 → 该 CLI 原生 schema。放该 runtime 文件内（对齐 claude_code `_entry_to_claude` 先例）。

---

## 2. OpenCode 接入（本期，可做可测）

### 2.1 事实基线（2026-06-04 本机实测）

- 版本 v1.15.10；`opencode mcp {add,list,...}` 子命令存在。
- `opencode run` **无** `--mcp-config` flag → 配置驱动。
- 配置精度链（opencode 官方 docs）：remote(.well-known) → 全局 `~/.config/opencode/opencode.json` → 项目 `<cwd>/opencode.json`（最高）→ `OPENCODE_CONFIG` env（custom override）；**merge 非 replace**。
- **实测**：`OPENCODE_CONFIG=<tmp> opencode mcp list` → 临时文件里的 MCP server 出现；不设则为空。→ **逐进程隔离通道确认**。
- 现状：`opencode_runtime.py` 每次 `stream()` spawn 新进程（非长驻池化）；已会写全局 `~/.config/opencode/opencode.jsonc` 注 provider apiKey（`_write_provider_config`）。

### 2.2 schema 翻译表

| canonical（build_mcp_config_entry） | opencode `mcp.<name>` 值 |
|---|---|
| `{type:"stdio", command:"cmd", args:["a","b"], env:{K:V}}` | `{type:"local", command:["cmd","a","b"], environment:{K:V}, enabled:true}` |
| `{type:"sse", url:"https://..", headers:{..}}` | `{type:"remote", url:"https://..", headers:{..}, enabled:true}` |
| `{type:"http", url:"https://.."}` | `{type:"remote", url:"https://..", enabled:true}` |

差异点（易错）：① `command` 合并为**数组**；② `env` → `environment`；③ 必带 `enabled:true`；④ opencode 远程统一 `remote`（不分 sse/http）。

### 2.3 实现步骤（文件级）

**[MOD] `src/backend/app/infrastructure/llm/opencode_runtime.py`**

1. 加纯函数 `_entry_to_opencode(entry: dict) -> tuple[str, dict]`：返回 `(name, opencode_value)`，按 §2.2 翻译。
2. 加 `_write_opencode_config(provider, api_key, mcp_servers, memory_url, agent_id) -> str|None`：
   - 写**自包含**临时文件（`tempfile`，`prefix="agenthub_oc_"`，`delete=False`，`atexit` 清理——对齐 claude_code `_write_mcp_config`）。
   - 内容 = provider 块（复用现有 `_OPENCODE_CONFIG_TEMPLATE` 逻辑）+ `mcp` 块。
   - `mcp` 块合并：`agenthub-memory`（`{type:"remote", url:f"{memory_url}?agent_id={agent_id}", enabled:true}`，仅当 memory_url+agent_id 有值）+ 每条 `request.mcp_servers` 经 `_entry_to_opencode`。
   - 无任何 mcp 且 provider 已由全局覆盖时，可返回 None（退化为现状）。**推荐恒写自包含**，规避 merge/replace 歧义。
3. `stream()` 内：调用 `_write_opencode_config(...)` 拿 `cfg_path` → `env["OPENCODE_CONFIG"] = cfg_path`。
   - `request.mcp_servers` 与 `request.agent_id` 已在 AgentRequest（ADR-05）；`memory_url = settings.mcp_memory_url`。
4. 保留现有 `_write_provider_config`（全局）作兜底 **或** 改为只走自包含临时文件（二选一，实现时定；自包含更干净，但要确保 provider 字段完整）。

**不改**：`_parse_line`、session 续接（`_session_map`）、超时/退出逻辑。

### 2.4 测试（T-05 必测）

**[NEW] `src/backend/tests/test_mcp_opencode_inject.py`**
- `_entry_to_opencode` 三形态：stdio（含 args/env→command 数组+environment）、sse、http。
- `_write_opencode_config`：① 含绑定 server → 临时文件 `mcp` 块正确；② 含 memory_url → `agenthub-memory` remote 条目；③ 空绑定 → 行为符合（None 或仅 provider+memory）。
- 断言写出的 JSON 可被 `json.loads` 且结构匹配 opencode schema。

**冒烟（可选，非 CI）**：`OPENCODE_CONFIG=<生成文件> opencode mcp list` 应列出注入的 server（本会话已验证手法可行）。

### 2.5 验收

- `scripts/verify.bat` 绿（ruff+mypy+tsc+eslint）。
- 新单测绿；既有 26 MCP 测试不回归。
- 一个绑定了 MCP 的 opencode agent，`stream()` 时进程 env 带 `OPENCODE_CONFIG`，配置含该 server——群聊同 workspace 的另一 agent 不受影响（零串号，逐进程 env 天然保证）。

### 2.6 风险

| 风险 | 处置 |
|------|------|
| `OPENCODE_CONFIG` 是 merge 还是 replace 不确定 | 写**自包含**配置（provider+mcp 都在），两种语义下都正确 |
| opencode 远程 MCP OAuth | 本期只接 stdio(local)+无认证 remote；OAuth remote 留后续 |
| stdio MCP server 在容器内缺二进制 | 与 claude_code 同类问题，沿用现状（CLI 自行报错透传），不在本计划兜底 |

---

## 3. Pi Agent seam（保持 deferred）

### 3.1 为何不落码

本机无 `pi` 二进制、无可查源码、CLI 无确认 MCP flag → **无法运行验证**。按「可观测验证」红线 + T-05（Adapter 必测），不写无法测的 adapter 代码。

### 3.2 seam 落点

**[MOD] `src/backend/app/infrastructure/llm/pi_agent_runtime.py::_build_cmd`**
- 在构造 cmd 处加注释锚点：
  ```python
  # NB-02: MCP 注入 seam — blocked on upstream pi CLI MCP support（见 ADR-06 §2.3 / RT-MCP §3）
  # 解除条件：确认 pi CLI 的 MCP config 或 extension 通道存在 → 按 ADR-06 统一原则
  #   把 request.mcp_servers 经 _entry_to_pi 翻译 + 逐调用通道注入 + 实测。
  ```
- 不加任何分支逻辑（避免死代码 / 误导）。

### 3.3 解除 deferred 的前置 checklist

1. 装到 pi CLI（二进制或源码）。
2. 查 MCP 通道：`pi --help` 找 mcp/config flag；查 extension API 文档；查是否读某配置文件。
3. 有逐调用通道 → 写 `_entry_to_pi` + 注入 + `test_mcp_pi_inject.py` + 冒烟实测 → 拉回本期。
4. 仅全局通道 → 评估串号风险（pi session 是否逐进程隔离）；无逐调用通道 → 上游提 issue，维持 deferred。

---

## 4. 后续 CLI（codex / gemini，均未实现 Runtime）

接入时套 ADR-06 统一原则，不在本计划展开实现：

| CLI | 配置 | MCP 字段 | 逐调用通道 | 翻译要点 |
|-----|------|---------|-----------|---------|
| codex | `~/.codex/config.toml` | `[mcp_servers]` | `CODEX_HOME=<tmpdir>` 或 `-c key=val` override | canonical → TOML；逐调用临时 CODEX_HOME 目录 |
| gemini | `~/.gemini/settings.json` | `mcpServers` | 项目 `.gemini/settings.json` 或 env | canonical → settings.json schema |

通用接法：① 找逐调用通道（绝不改全局）；② 写 `_entry_to_<cli>` 翻译；③ 自包含临时配置；④ T-05 单测 + 冒烟。

---

## 5. 执行顺序与闸门

```
本会话（已完成，docs-only）
  ├─ ADR-06 冻结统一原则 ✅
  ├─ §MCP.2 spec 同步（PR-09）✅
  ├─ 本 RT-MCP 施工蓝图 ✅
  └─ README-REVISION §9 R11 + roadmap §十 P2 交叉引用同步

下一会话（代码，opencode）
  1. opencode_runtime: _entry_to_opencode + _write_opencode_config + OPENCODE_CONFIG 注入
  2. test_mcp_opencode_inject.py（T-05）
  3. pi_agent_runtime: seam 注释（§3.2）
  4. verify.bat 绿 + 既有测试不回归
  5. worklog + STATUS 更新；按需 merge main（袁常驻权限）
```

**闸门**：
- ✅ 不触发 PR-01（不动数据模型/API 端点；请求携带链路 P2 已通）。
- ✅ PR-09：本会话 §MCP.2 已同步；代码会话无新增架构改动。
- ✅ T-05：opencode 翻译/写入必测；pi 不落码故无测试义务（seam 仅注释）。
- ✅ AR-02：只扩展 Adapter（runtime 翻译+注入），不另起运行时。

---

## 6. 与单一权威的关系

本文件 = README-REVISION §9 R11 的施工细化，受 ADR-06 约束。若与 README-REVISION 冲突，以 README-REVISION + ADR-06 为准。代码落地后，本文件的「下一会话」段标记完成并在 roadmap §十 P2 行更新状态。
