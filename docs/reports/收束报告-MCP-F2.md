# 收束报告 — MCP F2（Agent 绑定 + MCP 注入）

> 收束节点：MCP 功能 v1 · 收束-2（F2） | 日期：2026-06-04 | 主导：袁（Claude Agent 协助）
> 范围：P2 F2 接入批次（commit `0714d76`..`d938000`，均已在 `main`）
> 模式：单人项目（袁 + Claude）——AI 广覆盖扫描 + 袁自验签核（merge-to-main 常驻权限）
> 关联：[ADR-05](../../worklogs/decisions/0005-mcp-attach-request-carried.md)（请求携带）· [ADR-06](../../worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md)（统一注入原则）· [RT-MCP-V1.0](../plan/后续升级计划/MCP接入/06-详细设计/RT-MCP-V1.0-20260604.md) · [收束报告-F1](收束报告-MCP-F1.md)

---

## 0. 批次概述

| 项 | 内容 |
|----|------|
| 功能点 | F2 Agent 绑定（bind/unbind）+ 请求携带 attach（ADR-05）+ claude_code 注入 + opencode 注入（ADR-06）+ pi_agent NB-02 seam |
| 提交 | `0714d76` P2 核心（绑定+attach）→ `b542698` R11 运行时审计 → `d1eed06` /api/mcp 路径分离 → `ebfd007` ADR-06 方案冻结 → `e17b6ff` opencode 落码 → `d938000` opencode E2E 冒烟（均 Conventional Commits） |
| 代码 | `mcp_binding_service`（bind/unbind）+ binding repo + `AgentRequest.mcp_servers` + `build_request_mcp_servers` + `ContextBuilder.mcp_resolver` + claude_code `_write_mcp_config` + opencode `_entry_to_opencode`/`_build_opencode_mcp`/`_write_opencode_config`/`OPENCODE_CONFIG` 注入 + pi_agent seam 注释 + alembic 0010（部分唯一） |
| 测试 | `tests/test_mcp.py`（含 binding）+ `tests/test_mcp_opencode_inject.py`（8）→ **MCP 专项 34 用例** |

---

## 1. 阶段一：整理

| 检查项 | 结果 |
|--------|------|
| 未使用 import/函数/变量 | ✅ ruff `All checks passed`（MCP + LLM runtime 全量） |
| 注释代码块 / 调试代码 | ✅ 无（ruff T20 print 检查全过；grep TODO/FIXME/XXX 于 MCP 代码无命中） |
| 硬编码密钥 | ✅ 无（api_key 经请求/settings 注入，临时配置 atexit 清理） |
| 孤儿模块 / 依赖黑洞 | ✅ 无（翻译函数被 `stream()` 调用；binding service 被 router/deps 引用） |
| worklog 齐全 | ✅ `worklogs/袁/2026-06-04_MCP-opencode注入落码.md`（含 E2E 冒烟段） |
| 临时脚本清理 | ✅ E2E 冒烟脚本（`/tmp/oc_*.py`）已删，未入库 |
| STATUS / roadmap | ✅ 已更新（袁行 + 技术债表 R11 校正 + roadmap §十 P2 行） |
| 决策提升 ADR | ✅ ADR-05（请求携带）+ ADR-06（统一注入原则）+ RT-MCP 施工蓝图 |

**整理结论**：无熵增残留。

---

## 2. 阶段二：测试

### 自动化测试（SQLite + fakeredis）
- **MCP 专项**：`tests/test_mcp.py` + `tests/test_mcp_opencode_inject.py` → **34/34 通过**，覆盖三路径（T-03）：
  - binding：bind 创建、重复绑定 409（部分唯一）、unbind 软删、`build_request_mcp_servers` 装配条目
  - opencode 翻译：stdio（args/env→command 数组+environment）/sse/http 三形态 + 记忆+绑定组装 + 空 + 自包含写入（deepseek/通用 provider）
- **全量**：`pytest` → **118 passed / 2 failed**（另次序运行 116/4）——失败集**非确定性**，全部落在既有 flaky/环境簇。

### 失败项分析（均与本批次无关，跨运行非确定性）
| 失败 | 原因 | 归类 |
|------|------|------|
| `test_pi_agent_e2e::test_subprocess_lifecycle` / `::test_factory_routing` | 本机 Windows 未装 pi CLI（`FileNotFoundError`） | 🟢 环境 |
| `test_context_builder::test_group_delta_only_after_watermark` | 模块级 fakeredis 单例共享（全序失败、单跑绿） | 🟡 既有测试隔离债（F1 收束已记） |
| `test_selector::test_llm_failure_degrades_to_done` | LLM 环境敏感 | 🟡 既有债（F1 收束已记） |

> **零回归证据**：opencode/pi 改动 `git stash` 复核——在干净 P2 代码（`ebfd007`）上 pi/selector 三条同样失败 → 失败 pre-existing，非本批次引入。MCP 34 用例确定性全绿。

**测试结论**：本批次代码 100% 通过；全量失败为既有环境/隔离债（F1 已立项），权威跑测在 Docker。

---

## 3. 阶段三：审计（AI 线 + 袁自验线）

### 3.1 AI 审计线（全量扫描）

| 维度 | 检测 | 结果 |
|------|------|------|
| AR-01 5 层洋葱 | grep `domain/mcp/` 的 sqlalchemy/fastapi/infrastructure import | ✅ 零依赖上层/框架/ORM |
| AR-02 只扩展 Adapter | opencode/pi 仅在既有 `*_runtime` 内扩展（无新进程池/运行时/eventbus）；`attach`=请求携带（ADR-05），runtime 无状态 | ✅ |
| AR-06 system-model 解耦 | 注入逻辑读 `request.mcp_servers`，不在 domain 引入 CLI 概念 | ✅ |
| CR（ruff 全集 + T20） | `ruff check` MCP + LLM runtime | ✅ All checks passed |
| CR-12 禁同步阻塞 | opencode 注入为同步文件写（spawn 前一次性，非 IO 循环），claude_code 同模式 | ✅ 一致 |
| PR-03 Conventional | P2 全 commit 合规（feat/docs/test/fix/merge） | ✅ |
| PR-09 SPEC 同步 | `01-architecture §MCP.2` + README-REVISION §9 R11 + roadmap §十 P2 三处同步 | ✅ |
| AP-02 错误信封 | binding service 用 `E_MCP_BINDING_CONFLICT` 等域异常 → 全库沿用 `{detail}` | ⚠️ 已知 defer（R9，NB-02） |
| T-05 Adapter 必测 | opencode 翻译/写入 8 单测；claude_code 注入既有；pi **不落可执行代码故无测试义务**（仅 seam 注释） | ✅ |
| 串号风险（ADR-05/06 核心） | opencode `OPENCODE_CONFIG` 逐进程 env；claude_code `--mcp-config` 逐调用 flag——均逐进程隔离，群聊同 workspace 多 agent 零串号 | ✅ |

**AI 审计结论：无 🔴 红线违规。** 1 项 🟡（AP-02）为既有 defer，非本批次新违规。

### 3.2 袁自验线（merge-to-main 常驻权限，2026-06-04）

- [x] attach 机制：请求携带（ADR-05）规避池化 runtime 串号——**设计正确**
- [x] 统一注入原则（ADR-06）：逐调用隔离通道 > 全局 mutation——**口径认可**，opencode 拉回本期有本机实测支撑（非断言，纠 R11 盲区）
- [x] pi_agent 保持 deferred：本机不可验证 → 不落无法测的 adapter 代码——**符合可观测验证红线**
- [x] opencode 自包含临时配置规避 merge/replace 歧义——**清晰可接手**

> **袁自验结论：通过。** 收束-2（F2）AI 线 + 自验线双线通过，**闭合**。

---

## 4. 阶段四：效果验证

### 契约回演（§2.6 bindings）
| 端点/行为 | 契约要点 | 实现 |
|------|---------|------|
| POST /api/mcp/bindings | bind 创建，重复 409，解绑后可 rebind（部分唯一，alembic 0010） | ✅ |
| DELETE /api/mcp/bindings/{id} | 软删，下次 stream 自动不再携带（F-011） | ✅ |
| 请求携带 attach | active 绑定 → installation → server → `build_mcp_config_entry` → `AgentRequest.mcp_servers` | ✅ |

### 注入端到端验证（关键）
- **claude_code**：`--mcp-config <tempfile>` 合并记忆 + 绑定 servers（既有，F2 沿用）。
- **opencode 连接级 E2E 冒烟（2026-06-04，本机实跑）**：生产函数生成 `OPENCODE_CONFIG` → `opencode mcp list` 输出 `✓ everything connected`——opencode **真拉起 stdio MCP server 并完成 MCP initialize/tools 握手**，非仅解析配置。验证对象全为生产代码（含运行时 `_find_binary`）。
- **完整 chat→tool_call**：需真实 LLM provider key 跑 `opencode run`，超连接级冒烟范围 → 留 P4 带 key 端到端。
- **pi_agent**：deferred，seam 就位（解除门 RT-MCP §3.3）。

### 用户故事回溯
F2 让「Agent 绑定 MCP → 下次对话该 CLI 自动加载 MCP server」闭环在 claude_code + opencode 两个运行时可走通。方向对齐 PRD F2。**未偏离**。

### 技术债盘点（更新 STATUS）
| 问题 | 状态 |
|------|------|
| ~~MCP 注入 claude_code-only（R11）~~ | ✅ opencode 已拉回（ADR-06）；pi_agent 仍 deferred（待上游 MCP 支持） |
| 既有套件 flaky（fakeredis 模块单例 / selector LLM 敏感 / pi 二进制缺失） | 🟡 既有债（F1 已立项），非 MCP 引入 |
| 完整 chat→tool_call 端到端（需 LLM key） | 🟢 P4 带 key 验 |
| 工具级 tool_subset 过滤 | 🟢 P4（CLI 不一定支持工具级过滤） |
| AP-02 错误信封 / AP-05 版本 | 🟢 NB-02 |

---

## 5. 收束结论

| 阶段 | 结论 |
|------|------|
| 整理 | ✅ 无残留 |
| 测试 | ✅ MCP 专项 34/34；全量失败为既有环境/隔离债（非确定性，已立项） |
| 审计 | ✅ AI 线无红线；袁自验线通过 |
| 验证 | ✅ bindings 契约回演 + opencode 连接级 E2E 冒烟（`✓ connected`），方向未偏 |

**收束-2（F2）：AI 线 + 袁自验线双线通过，✅ 闭合（2026-06-04）。** 进入 P3（F3 创建 MCP）或 P4（F5 工具展示）。

### 关闭动作
- [x] 袁自验签核（§3.2，通过）
- [x] P2 各 commit 已在 `main`（袁授予直接合并权）
- [x] 本报告 + ADR-05/06 + RT-MCP 已提交
- [ ] roadmap §十 P2 行标记收束-2 闭合（随本报告提交）
