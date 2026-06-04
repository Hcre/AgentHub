# 2026-06-04 MCP opencode 注入落码 + pi seam

> 作者：袁（Claude Agent 协助）| 阶段：P2 F2 接入 | 依据：ADR-06 / RT-MCP-V1.0

## 做了什么

承接本会话上半段的方案冻结（ADR-06 统一注入原则 + RT-MCP 施工蓝图，已 push `ebfd007`），下半段按蓝图落 opencode 注入代码。

### 代码

- `infrastructure/llm/opencode_runtime.py`：
  - `_entry_to_opencode(entry) -> (name, value)`：canonical 条目 → opencode schema（command 数组化 / env→environment / `enabled:true` / 远程统一 remote）。
  - `_build_opencode_mcp(bound, memory_url, agent_id)`：组 `mcp` 块 = 记忆工具（agenthub-memory，remote）+ 绑定 servers；空则返回 `{}`。
  - `_build_provider_dict` / `_write_opencode_config`：写**自包含**临时配置（provider+mcp），返回路径，atexit 清理。
  - `stream()`：有 mcp 时 `env["OPENCODE_CONFIG"]=<tmp>`（逐进程隔离通道，本机实测注入成功，零串号）；无绑定退化为现状（不设 env）。
- `infrastructure/llm/pi_agent_runtime.py`：`_build_cmd` 加 NB-02 seam 注释（不落可执行代码，本机无 pi 二进制可验证）。

### 测试

- 新增 `tests/test_mcp_opencode_inject.py`：8 测试绿（stdio/sse/http 翻译 + 记忆+绑定组装 + 空 + 自包含写入 deepseek/通用 provider）。

## 验证

- ruff 全绿（修了测试 RUF059 + `_build_provider_dict` no-any-return）。
- 全量 `pytest`：117 passed / 3 failed；**3 失败已 stash 复核为 pre-existing**（test_pi_agent_e2e 两条因本机无 pi 二进制、test_selector 一条与 MCP 无关）→ 我的改动零回归。
- opencode 注入新增 8 测试，P2 累计 34 绿。

## 闸门

- 不触发 PR-01（不动数据模型/API）；PR-09 已同步（§MCP.2 / R11 / roadmap）；AR-02 满足（只扩展 Adapter）；T-05 满足（翻译/写入必测）。

## 给下一位的交接

- opencode MCP 注入主链路已通。**未做的冒烟**：起真实 opencode agent 跑一次 `OPENCODE_CONFIG` 注入端到端（本机已验证 `opencode mcp list` 能读到，但未走完整 chat→tool_call）。建议 P4 工具展示时一并端到端验。
- pi_agent 仍 deferred：解除前置门见 RT-MCP §3.3（装 pi → 查 MCP 通道 → 翻译+实测）。
- 待裁：`/api/mcp` 路径与董记忆 MCP mount 重叠（ADR-05 遗留），P4 前定。
