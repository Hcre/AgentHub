---
name: agenthub-dev
description: AgentHub 项目开发最佳实践 — 从 PR 任务到 commit push 的端到端 workflow，整合 feat-start / feat-complete / git-workflow / code-review / spec-driven-development / test-claude-adapter / doc-sync / deploy / frontend-style-edit / BDD+TDD / 5 层洋葱架构 + 11 类红线。Use this skill whenever you are developing for AgentHub (writing backend / frontend / spec / test / commit / push).
---

# AgentHub 开发最佳实践

> **整合范围**：把 AgentHub 项目开发时**跨 9 个根目录 skill** 的零散规则 + CLAUDE.md 红线 + 5 层洋葱架构 + BDD+TDD 流程 + STATUS/roadmap/PRD 协作约定 + 飞书文档沉淀协议，**收敛成一份单一可执行的最佳实践**。
>
> **适用时机**：领了 roadmap 任务 → 准备开发 → 写到 commit push 完整链路。
>
> **关联根目录 Skill**：`feat-start` / `feat-complete` / `git-workflow` / `code-review` / `spec-driven-development` / `test-claude-adapter` / `doc-sync` / `deploy` / `frontend-style-edit`。
>
> **关联规范**：[CLAUDE.md 红线总表 AR/CR/PR/AP/T/D](../../CLAUDE.md) · [01-architecture 5 层洋葱](../docs/conventions/01-architecture_架构设计规范.md) · [05-testing BDD+TDD 流程段](../docs/conventions/05-testing_测试规范.md) · [04-commands §六 BDD 验收场景](../docs/specs/04-commands_命令接口.md)

---

## 〇、动手前 5 问（每次任务开工前必走）

| # | 问 | 答错的后果 |
|---|----|----------|
| 1 | **我在做哪个 P 任务？** | 看 [roadmap §8 P0/P1/P2 任务表](../docs/plan/开发清单_roadmap.md)；找不到 = 没领任务，别开工 |
| 2 | **STATUS.md 别人在做什么？** | 不读 = 撞车 / 重复实现 |
| 3 | **BDD 场景在哪？** | [04-commands §六 BDD 验收场景](../docs/specs/04-commands_命令接口.md)；没 BDD = 任务未冻结，先写 BDD（spec-driven-development）|
| 4 | **红线是哪几条？** | [CLAUDE.md 红线速查表](../../CLAUDE.md)；违反 = 被打回 |
| 5 | **分支命名对吗？** | `feature/<domain>/<desc>`（PR-02）；不在 main 上开发（PR-07）|

**未答完 5 问 = 禁止动手**。

---

## 一、开发链路 7 步（每 P 任务必走 1 遍）

```
1. 领任务 + 读 spec  ──→  2. 写 BDD  ──→  3. 拉分支  ──→  4. 扫描仓库
                                                                 │
                                                                 ↓
   7. commit + push  ←──  6. 审查 diff  ←──  5. 实现 (TDD)
```

### 步骤 1：领任务 + 读 spec

```bash
# 0. 同步代码
git pull origin main
git checkout main

# 1. 读 STATUS.md 当前状态 + roadmap §8 P 任务表
# 2. 找 BDD 场景：04-commands §六（覆盖 P0-4/P1-2/P1-3 + 11 P2 缺口）
# 3. 读相关 spec：架构(01) / 数据(03) / 命令(04) / 测试(05)
```

**读不够的代价**：写出来的代码会被 CR 打回 / 跟 spec 不一致 / 重复造轮子。

### 步骤 2：写 BDD（如果 spec 还没 BDD 段）

**触发**：roadmap 任务找不到对应 BDD（如新加的 P2 任务）。

**Action**：
1. 打开 `docs/specs/04-commands_命令接口.md` §六
2. 找最相似的 BDD 段（如 P0-4 → `B-1-P0-04`），复制三件套（Given/When/Then）模板
3. 改 ID 为 `B-<PRD章节>-<P级别>-<序号>` 格式
4. 加到对应 PRD 章节下（如 6.1 IM 聊天 / 6.2 Orchestrator / ...）
5. 在 §七 BDD↔任务映射表追加一行
6. **commit 单独**：`docs(specs): add BDD B-1-P2-XX for <task>`

**为什么先 BDD**：BDD 是契约 → 实现必须满足契约 → TDD 用 BDD 转测试 → 测试驱动实现。

### 步骤 3：拉分支

```bash
# 分支命名（PR-02）：feature/<domain>/<desc>
#   domain ∈ {chat, group, agent, task, mcp, frontend, backend, infra, ...}
git checkout -b feature/<domain>/<short-desc>
# 例：
git checkout -b feature/chat/pin-session-ownership
git checkout -b feature/frontend/monaco-editor
git checkout -b feature/mcp/dry-run-validation
```

**为什么 feature/ 前缀**：PR 模板识别 + CI 自动跑测试 + pre-push hook 检查命名（scripts/check_branch.py）。

### 步骤 4：扫描仓库

**用工具（不是肉眼）**：

| 工具 | 用途 | 命令 |
|------|------|------|
| 代码图谱 | 看调用关系 / 影响范围 | `python scripts/gen_codegraph.py` → 查 `.codegraph/graph.json` |
| 影响分析 | 改 1 个模块会触发哪些测试 | 读图谱 `nodes[module].callers` + `edges` |
| 现存 spec | 看同领域怎么实现的 | `docs/specs/01b-architecture-design_分层与数据流.md` |
| 测试参考 | 看同模块怎么测的 | `src/backend/tests/` `src/frontend/src/__tests__/` |

**为什么扫仓库**：避免重复实现 + 了解现有模式 + 影响分析（改 1 个字段 = 改 3 个文件？）。

### 步骤 5：实现（TDD 红 → 绿 → 重构）

**TDD 循环**（每个 BDD 场景 1 轮）：

```
红：写失败测试（基于 BDD Given/When/Then 转 AAA 模板）
    │
    ↓
绿：最小实现让测试通过（删多余逻辑 / 加 stub / 写 happy path）
    │
    ↓
重构：清掉代码坏味道（命名 / 拆分 / 抽函数）保持测试绿
```

**AAA 模板**（来自 [05-testing §二](../docs/conventions/05-testing_测试规范.md)）：

```python
def test_<方法>_<场景>_<期望>():
    # Arrange（Given）— 准备数据 + fixture
    msg = ChatMessage(content="@FrontendAgent 帮我看看", mentions=["FrontendAgent"])
    router = DispatchRouter()
    # Act（When）— 调用被测函数
    result = router.resolve(msg, mode="auto")
    # Assert（Then）— 断言结果
    assert result.target_type == "agent"
    assert result.target_id == "FrontendAgent"
```

**命名规范**（强约束）：
- Python: `test_<方法>_<场景>_<期望>`（`snake_case`）
- TypeScript: `test_<method>_<scenario>_<expected>` 或 vitest `describe()` + `it()`

**覆盖率门禁**（per [05-testing §三 覆盖率目标](../docs/conventions/05-testing_测试规范.md)）：

| 模块类型 | 行覆盖 | 分支覆盖 |
|----------|--------|---------|
| 核心 domain（task_engine / coordinator / FSM）| ≥ 90% | ≥ 85% |
| Service / Application（L3）| ≥ 80% | ≥ 70% |
| API 层（L4）| ≥ 80% | ≥ 70% |
| Infrastructure / Adapter（L1）| ≥ 70% | ≥ 60% |
| 前端组件 | ≥ 70% | ≥ 60% |
| 前端 store / hook | ≥ 80% | ≥ 70% |

**CR 必查 6 条红线**（违反 = 打回）：

| 红线 | 含义 | 自动抓 |
|------|------|------|
| T-01 | 测试独立（不依赖顺序）| `pytest -p no:randomly` 乱序跑全绿 |
| T-02 | 只 Mock 外部边界（LLM API）| CR 审 |
| T-03 | 覆盖正常+边界+异常 | CR 审 + 分支覆盖率 |
| T-04 | 无 flaky test | CI 重试检测 |
| T-05 | Adapter 覆盖 成功/限流/超时/key失效/流式中断 | CR 审 |
| T-06 | FSM 覆盖 合法/非法/幂等 | CR 审 |

### 步骤 6：审查 diff

```bash
# 1. 看 staged + unstaged
git status
git diff --staged

# 2. 看 commit 后 diff
git log -p -1

# 3. 跑 lint + typecheck + test
scripts/verify.bat    # ruff + mypy + tsc + eslint
# 或
cd src/backend && pytest -q
cd src/frontend && npm test

# 4. 跑 docs check
python scripts/check_docs.py
python scripts/check_worklog.py
```

**CR 自查**（参考 [code-review skill](../../skills/code-review/)）：
- AR-01~06 架构红线（5 层洋葱 / Adapter / Harness / FSM）
- CR-01~12 代码红线（async / 类型 / import / 注释块）
- PR-01~09 流程红线（接口冻结 / 分支 / Conventional Commits / 2 人 Review）
- AP-01~07 API 红线（kebab / `{error}` / JWT / Pydantic / 版本 / 兼容 / WS request_id）
- T-01~06 测试红线

### 步骤 7：commit + push

**commit 风格**（[03-git PR-03](../docs/conventions/03-git_Git协作规范.md) Conventional Commits）：

```bash
# 格式：<type>(<scope>): <subject>
#   type ∈ {feat, fix, docs, refactor, test, chore, perf, ci, build, style}
#   scope ∈ 模块名（chat / group / mcp / frontend / ...）
#   subject 中文 ≤ 50 字，祈使语气，结尾无句号

# 例：
git add src/backend/app/api/routers/messages.py
git commit -m "fix(messages): pin API 加 session 所有权校验 (B-1-P0-04 修复 gap #3)"

git add src/frontend/src/components/MessageBubble.tsx
git commit -m "feat(frontend): 全屏预览 modal 组件 (B-4-P2-D02)"

git add docs/specs/04-commands_命令接口.md
git commit -m "docs(specs): 增 BDD §六 覆盖 P0-4/P1-2/P1-3 + 11 P2 缺口"
```

**scope-enum 校验**（commitlint pre-commit）：
- `agent` / `group` / `session` / `message` / `task` / `mcp` / `frontend` / `backend` / `infra` / `docs` / `roadmap` / `worklog` / `status` / `harness` / `deps`

**commit 拆分原则**（per [CLAUDE.md 行为准则](../../CLAUDE.md)）：
- ✅ 1 commit 1 件事
- ✅ 文档单独 commit（`docs(specs): ...`）
- ✅ 测试单独 commit（`test(chat): ...`）或跟随实现 commit
- ❌ 1 commit 跨 3 个模块（拆）

**push 策略**：
- user 偏好（2026-06-07 落档）：**直接 push main**，不走 PR 流程
- pre-push hook 会跑：check_worklog.py（worklog 更新）+ check_docs.py（文档命名）+ check_branch.py（分支命名）+ check_secrets.py（密钥扫描）

```bash
git push origin <branch>  # user 偏好直推 main
# 或
git push origin main      # user 偏好
```

**commit 后必做**：
1. 更新 `STATUS.md`（你的那一行：正在做 → 完成了什么 + 阻塞？）
2. 写 worklog（`worklogs/<你的名字>/YYYY-MM-DD_<简短>.md`）— per [worklog template](../../worklogs/template.md)
3. 跑 `scripts/check_worklog.py` 验证

---

## 二、5 层洋葱架构（CR 必守 AR-01~06）

```
L5 Presentation (React UI)        ← 前端 src/frontend/src/
    │   HTTP/WS 调用 ↓
L4 API (FastAPI routers)          ← src/backend/app/api/
    │   服务调用 ↓
L3 Application (services)         ← src/backend/app/application/
    │   编排 + 业务流程 ↓
L2 Domain (entities / FSM / rules) ← src/backend/app/domain/
    │   抽象接口 ↑
L1 Infrastructure (DB / Adapter)  ← src/backend/app/infrastructure/
    ↑   依赖倒置（DIP）：L1 实现 L2 接口，不允许 L2→L1 反向依赖
```

**关键约束**（[01-architecture §4](../../docs/conventions/01-architecture_架构设计规范.md)）：

| 红线 | 内容 |
|------|------|
| **AR-01** | 必须 5 层洋葱，模块不跨层 |
| **AR-02** | 新 Agent 系统只加 Adapter（`infrastructure/llm/<system>_runtime.py`），不改 L2/L3 |
| **AR-03** | Harness（`application/harness/`）无 LLM，只做 DAG 调度 + asyncio.gather |
| **AR-04** | Agent 不直通（必须经 Harness 调度，例外：私聊 1v1 可直）|
| **AR-05** | FSM 状态转换必须事件溯源（`task_events` 表追加 + 重放）|
| **AR-06** | system-model 解耦（`system_settings` 表，不写死 enum）|

**L1→L2 注入示例**（CR-01 必读）：

```python
# domain/llm/protocol.py
class AgentRuntime(Protocol):
    async def stream(self, request: AgentRequest) -> AsyncIterator[str]: ...
    def attach_mcp(self, servers: list[dict]) -> None: ...  # MCP F2 扩展点

# infrastructure/llm/claude_code_runtime.py
class ClaudeCodeRuntime:
    def __init__(self, cli_path: str = "claude"): ...
    async def stream(self, request: AgentRequest) -> AsyncIterator[str]:
        # 真 CLI subprocess 调用
        ...
```

---

## 三、5 大核心工程红线（必须记牢）

| 红线 | 速记 | 反例 |
|------|------|------|
| **CR-03 Alembic 禁手动改表** | 改 schema 必走 migration | 直接 psql `ALTER TABLE` → 下次 migrate 失败 |
| **CR-07 TypeScript strict** | `tsconfig.json` 必 strict | 任何 `any` → 编译告警 |
| **CR-08 组件 < 200 行** | 拆细 | MessageBubble 800 行 → 拆 4 文件 |
| **CR-09 hooks 抽离** | 业务逻辑不写组件 | 组件内有 useEffect fetch + setState → 抽 useXxx hook |
| **CR-12 禁同步阻塞** | async all the way | FastAPI 路由用 `requests.get` → 改 httpx async |

详见 [02-coding 12 条红线](../../docs/conventions/02-coding_代码编写规范.md)。

---

## 四、API 设计 7 红线（动 /api/* 必看）

| 红线 | 含义 |
|------|------|
| **AP-01** | URL kebab-case（`/api/agent-tasks`）非 snake_case |
| **AP-02** | 错误响应 `{error:{code:"E_XXX", message:"..."}}`（Pydantic 422 沿用 `{detail}` 是历史兼容）|
| **AP-03** | 必走 JWT（`Authorization: Bearer <token>`）|
| **AP-04** | body 必 Pydantic model 校验 |
| **AP-05** | 版本前缀（**本期 AP-05 暂缓**，per [ADR-0003](../../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md)）|
| **AP-06** | 兼容：删字段必 deprecated 标签，加字段可后向兼容 |
| **AP-07** | WS 事件必带 `request_id`（AP-07） |

详见 [04-api 7 条红线](../../docs/conventions/04-api_API设计规范.md)。

---

## 五、文档沉淀 12 红线（D-01~12）

| 红线 | 含义 | 自动抓 |
|------|------|------|
| **D-05~10** | 命名合规（`{English}_{Chinese}.md` / `YYYY-MM-DD_*.md` / `NNNN-*.md` ADR）| `scripts/check_docs.py` |
| **D-11** | CLAUDE.md 链接全有效 | `scripts/check_docs.py` |
| **D-12** | pre-commit / pre-push hooks 已装 | `scripts/check_docs.py` |

**写新文件前**：查 [meta/FILE_GRAPH.md](../../meta/FILE_GRAPH.md) §三「文档放哪」决策树。

---

## 六、飞书文档沉淀协议（Mavis owner 必走）

> 课题「AI 协作能力 30%」考察点 = "沉淀出和 ai 协作的 Spec、skill、rules 等协作规范"。

**触发**：每完成 P 任务收束（plan_complete=true）→ 24h 内更新 [飞书 AI 协作开发记录](../../docs/deliverables/AI协作开发记录.md)。

**写入内容**：
- 章节段：a 项目背景 / b AI 协作流程 / c Spec/Skill/Rules 沉淀 / d commit 工作流 / e 已知 gap / f 后续计划
- 单段 CJK 字节 ≥ 200（不要全是英文 / 不要一行段）
- 链接 relative（`docs/deliverables/...`），不写 `https://feishu.cn/...` 绝对 URL（per `82b265a` commit 12 处链接修复）
- 避免 `>` / `<` 等 Markdown 保留字符（per `82b265a` CJK 编码修复）

**AI 汇报 vs 飞书文档区别**：
- AI 汇报（对话内联）：每功能点完成 → 立即汇报
- 飞书文档（落盘）：每收束节点 → 整段落档

---

## 七、ADR（架构决策记录）触发条件

> 写新 ADR 当（且仅当）以下任一满足：
> - 选了关键技术（X 库 vs Y 库）
> - 改了 5 层洋葱 / 加 Adapter / 改 FSM
> - 改了数据模型（增删表 / 改字段语义）
> - 改了 API 契约（PR-01 冻结前）
> - 改了 CI / 测试 / 部署流程
> - 推迟 / 暂缓 / downscope 某任务（如 E 视觉 downscope）
> - Mavis owner 委派决策（per [ADR-0008](../../worklogs/decisions/0008-self-governance-authorization.md) 自主决策授权）

**命名**：`worklogs/decisions/NNNN-<slug>.md`（NNNN = 4 位递增）

**模板**：

```markdown
# ADR-NNNN: <title>

- **状态**: Proposed / Accepted / Deprecated
- **日期**: YYYY-MM-DD
- **决策者**: 黎 / 董 / 袁 / Mavis
- **关联 Spec**: docs/specs/XX-xxx.md §X
- **关联 BDD**: 04-commands §六 B-X-PY-ZZ

## 背景
<要解决的问题>

## 决策
<选择 A 而不是 B/C 的原因 + 选了什么>

## 影响
<正面 / 负面 / 后续 TODO>

## 替代方案
- 方案 B: <内容> — 为什么不选
- 方案 C: <内容> — 为什么不选
```

**已有 11 篇**：[0001 CLI 优先](../../worklogs/decisions/0001-cli-first-pivot.md) / [0002 长驻 CLI](../../worklogs/decisions/0002-phase1-long-running-cli.md) / [0003 MCP URL+AP-05 暂缓](../../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md) / [0004 MCP F1 落地口径+安装探针](../../worklogs/decisions/0004-mcp-f1-landing-and-installer-seam.md) / [0005 MCP attach=请求携带](../../worklogs/decisions/0005-mcp-attach-request-carried.md) / [0006 MCP 注入逐进程隔离通道](../../worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md) / [0007 Tauri 桌面 App pivot](../../worklogs/decisions/0007-tauri-desktop-pivot.md) / [0008 自主决策授权](../../worklogs/decisions/0008-self-governance-authorization.md) / [0009 P2 handoff cron](../../worklogs/decisions/0009-p2-handoff-cron.md) / [0010 E 视觉 downscope](../../worklogs/decisions/0010-integration-verify-downscope-e.md) / [0011 plan_bcf9945c complete](../../worklogs/decisions/0011-plan-bcf9945c-complete.md)。

---

## 八、commit 风格（Conventional Commits + scope-enum）

```bash
# 格式：<type>(<scope>): <subject>
#   type  : feat | fix | docs | refactor | test | chore | perf | ci | build | style
#   scope : agent | group | session | message | task | mcp | frontend | backend | infra | docs | roadmap | worklog | status | harness | deps
#   subject: 中文 ≤ 50 字，祈使语气，无句号

git commit -m "feat(mcp): market list 端点 + 5 单测 (B-X-PY-ZZ)"
git commit -m "fix(messages): pin API session 所有权校验 (B-1-P0-04)"
git commit -m "docs(specs): 增 BDD §六 覆盖 P0-4/P1-2/P1-3"
git commit -m "test(chat): pin 7 + copy 4 单测 (B-1-P0-04 配套)"
git commit -m "chore(gitignore): 排除 _work/_dbg debug 产物"
```

**多 commit 拆分**（per [03-git PR-03](../../docs/conventions/03-git_Git协作规范.md)）：
- ✅ 1 commit 1 主题（实现 + 测试可同 commit）
- ✅ 文档 commit 单独（`docs(specs):` / `docs(roadmap):` / `docs(worklog):`）
- ❌ 1 commit 跨多模块（拆）

---

## 九、E2E + 集成验证协议（per 凌晨冲刺 6 E2E 模式）

**触发**：P 任务完成后做 E2E + 集成验证（STATUS.md 验证段必须填）。

**协议**：

```bash
# 1. 起服务（local uvicorn 优于 docker image，避免 image 滞后）
cd src/backend && uvicorn app.main:app --port 8766

# 2. 跑 Playwright E2E（5+ 章节）
python scripts/e2e_<feature>.py --base http://localhost:8766

# 3. 写 6 E2E 验证报告 docs/deliverables/integration-verify-<feature>.md
#    含：每章节 1 行（Given/When/Then + 截图链接 + PASS/FAIL）

# 4. 截图存 docs/deliverables/screenshots/e2e-<feature>-F1..F6-*.png
#    用 Playwright getByRole 精准定位（不用 cu 视觉）
```

**E2E 6 章节样例**（凌晨冲刺 v4 模式）：
- A iframe-sandbox ✓ / B colored-diff ✓ / C Pin/Unpin ✓ / D 复制代码 ✓ / E S5 inbox FAIL（已知 downscope）/ F 1KB upload ✓

**6 E2E 模板**：

```python
# scripts/e2e_<feature>.py
# 章节 A: <功能 1>
assert page.get_by_role("button", name="Pin").is_visible()
# 章节 B: <功能 2>
...
# 章节 F: <上传 / 边界>
```

---

## 十、demo 录制协议（替代 v4 wallpaper 残留）

**已知 gap**（per [STATUS.md line 34 + worklog 12-E2E.md](../../worklogs/mavis/2026-06-07_E2E视觉验证+群聊Pin+UX修复.md)）：v4 wallpaper 44.9% 残留（v5 SetWindowPos crash 失败）。

**v6 协议**（per agent memory「Playwright 录 demo 视频核心约束」）：

```python
# scripts/demo_v6.py
# 1. Chrome 启动参数：--start-maximized（不要 Win32 SetWindowPos）
context = browser.new_context(viewport={"width": 1920, "height": 1080})
# 2. ffmpeg gdigrab 录屏：-i desktop -video_size 1920x1080
subprocess.Popen(["ffmpeg", "-f", "gdigrab", "-i", "desktop",
                  "-video_size", "1920x1080", "-framerate", "30",
                  "docs/deliverables/video/raw-recording-v6.mp4"])
# 3. 6 章节脚本（13KB 6 章节 + 7 TTS + 27 字幕 + 2 AI cover）
# 4. 合成 mp4：h264 + aac + mov_text 字幕 zho
```

**录制后验证**：
- `ffprobe <mp4>` → 1920x1080 + h264 + aac + 字幕流
- 人工 review → 无明显 wallpaper 残留

---

## 十一、STATUS.md 协作约定（**每 push 必更新**）

| 时机 | 改什么 |
|------|------|
| 领新任务 | 「正在做」列写新任务 + 「阻塞？」列写依赖 |
| 完成 commit | 「这周完成了」列追加 `+ commit XXXX <简述>` |
| 阻塞 | 「阻塞？」列写「⚠️ 需 XX 答 Q1」 |
| 收束节点 | 在「⏭️ 进行中交接」加整段（参考 2026-06-07 凌晨冲刺 5 task 收束模板）|

**STATUS ↔ Git 映射**（per [scripts/check_worklog.py](../../scripts/check_worklog.py)）：

| Git user.name | STATUS 行 |
|---------------|----------|
| oldmanpushbike | 黎 |
| yii.d | 董 |
| xiangbianpangde | 袁 |
| Mavis 凌晨冲刺 | 写「Mavis owner」临时行 |

**不知道是谁？**：`git config user.name` → 查 STATUS.md Git↔目录映射表。

---

## 十二、避免常见错误（Mavis owner 历次踩坑）

| 错 | 正确 |
|----|------|
| 在 main 上开发 | `feature/<domain>/<desc>` 分支 |
| 1 commit 跨 3 模块 | 拆 3 commit，按模块 |
| 写 BDD 漏边界 | 必加「错误 401 / 422 / 404 / 边界 1/2/3」|
| 集成验证用 docker backend image（image 滞后）| local uvicorn :8766 |
| 录 demo 用 Win32 SetWindowPos | Chrome `--start-maximized` + ffmpeg gdigrab |
| 写工作日志用 PS 5.1 管道（`Get-Content \| Set-Content`）| 用 Read/Write/Edit 工具（UTF-8 直通）|
| 写文档用 `https://feishu.cn/...` 绝对 URL | relative 路径 `docs/...` |
| CJK 字符里含 `>` `<` 触发 Markdown 解析 | 改用全角 `＞` `＜` 或反引号包裹 |
| frontend 改代码 rebuild image（3min）| vite dev container + volume mount（<1s HMR）|
| cu (Computer Use) 测 demo 视觉 | playwright MCP（DOM 精准，不丢 Chinese 编码）|
| S5 inbox 在 demo 视频演示（backend TODO）| 替换为「任务看板演示」+ ADR-0010 downscope |
| MCP 路径写 `/api/v1/mcp/...` | `/api/mcp/...`（per ADR-0003）|
| MCP WS 事件写扁平 `{"event":...}` | 信封 `{"type":"...","payload":{...},"request_id":...}`（per AP-07）|

---

## 十三、AgentHub 任务清单速查（最新状态）

**M5/MVP 收尾冲刺**（per [roadmap §八](../../docs/plan/开发清单_roadmap.md)）：

| # | 任务 | 状态 | BDD |
|---|------|------|-----|
| P0-1 | 网页预览 iframe | ✅ | (已 E2E 验) |
| P0-2 | Diff 视图 | ✅ | (已 E2E 验) |
| P0-3 | 文件附件上传 | ✅ | (已 E2E 验) |
| P0-4 | Pin 消息 UI | ✅ 前端 / ⚠️ 后端校验 | `B-1-P0-04` |
| P0-5 | 复制代码/重新生成 | ✅ | (已 E2E 验) |
| P0-6 | Demo 数据集 + 录制脚本 | ✅ v4 残留 / 📋 v6 待做 | `B-6-P2-V01` |
| P1-1 | 工作目录 UI | ✅ | (已 E2E 验) |
| P1-2 | Token 消耗监控 | ⬜ | `B-5.3-P1-2` |
| P1-3 | CLI PATH 扫描 | ⬜ | `B-5.4-P1-3` |
| P1-4 | Playwright E2E 5 Story | ⚠️ 10 screenshot + 11 单测 | (需 CI gate) |

**MCP v1 阶段表**（per [roadmap §十](../../docs/plan/开发清单_roadmap.md)）：

| 阶段 | 状态 | 任务 |
|------|------|------|
| P0 整理+PR-01 草案 | ✅ | 路径校正 + 端点冻结 |
| P0.5 二次对账 | ✅ | R1-R10 schema↔代码 |
| P1 F1 市场 | ✅ 收束-1 | 4 表 + 5 端点 + 19 测试 |
| P3 F3 创建 | ⬜ | stdio/sse + 模板 + dry-run |
| P2 F2 接入 | ✅ 收束-2 | bind + claude_code/opencode 注入 + 34 测试 |
| P4 F5 展示 | ⬜ | 工具调用卡片 + WS 事件 |

**P2 缺口**（per STATUS.md PRD 对照段 ⚠️ 部分 6 / ❌ 未做 7）：
- ⚠️ 对话列表搜索/置顶 → `B-1-P0-S01` `B-1-P0-S02`
- ⚠️ 消息类型部署卡 → `B-5-P2-DP01`
- ⚠️ 消息操作回复/引用 → `B-1-P0-S03` `B-1-P0-S04`
- ⚠️ 文档渲染 → `B-4-P2-D01`
- ⚠️ 全屏预览 → `B-4-P2-D02`
- ❌ Monaco 编辑器 → `B-4-P2-D03`
- ❌ Orchestrator 失败降级 → `B-2-P2-F01` `B-7-P2-FD01`
- ❌ 移动端 H5 → `B-6-P2-M01`
- ❌ PPT 浏览 / 版本历史 / 对话式修改 / 桌面端（4 P3）

---

## 十四、检查清单（每 P 任务完成前必走）

- [ ] 5 问 答完（任务 / STATUS / BDD / 红线 / 分支命名）
- [ ] BDD 在 04-commands §六（无则先写）
- [ ] 分支 `feature/<domain>/<desc>`
- [ ] TDD 循环（红 → 绿 → 重构）
- [ ] 测试 6 红线（T-01~06）
- [ ] CR 自查（AR/CR/PR/AP/T/D）
- [ ] 6 E2E 验证（页面/接口/边界/失败）
- [ ] commit 风格（Conventional Commits + scope-enum）
- [ ] push 前 worklog 已写
- [ ] push 后 STATUS.md 已更新
- [ ] `scripts/check_docs.py` 0 错
- [ ] `scripts/check_worklog.py` 0 错
- [ ] 飞书文档（收束节点 24h 内更新）
- [ ] ADR 触发条件满足则写（[§七](#七-adr架构决策记录触发条件)）

---

## 十五、关联文档

| 方向 | 链接 |
|------|------|
| 红线总表 | [CLAUDE.md](../../CLAUDE.md) |
| 5 层洋葱 | [01-architecture_架构设计规范.md](../../docs/conventions/01-architecture_架构设计规范.md) |
| 5 大工程红线 | [02-coding_代码编写规范.md](../../docs/conventions/02-coding_代码编写规范.md) |
| Git 协作 | [03-git_Git协作规范.md](../../docs/conventions/03-git_Git协作规范.md) |
| API 7 红线 | [04-api_API设计规范.md](../../docs/conventions/04-api_API设计规范.md) |
| 测试 BDD+TDD | [05-testing_测试规范.md](../../docs/conventions/05-testing_测试规范.md) |
| 文档 D-01~12 | [06-documentation_文档规范.md](../../docs/conventions/06-documentation_文档规范.md) |
| BDD 验收场景 | [04-commands_命令接口.md §六](../../docs/specs/04-commands_命令接口.md) |
| 测试策略 | [05-testing-strategy_测试策略.md](../../docs/specs/05-testing-strategy_测试策略.md) |
| Roadmap 任务表 | [开发清单_roadmap.md §8](../../docs/plan/开发清单_roadmap.md) |
| 飞书协作记录 | [AI协作开发记录.md](../../docs/deliverables/AI协作开发记录.md) |
| 11 篇 ADR | [worklogs/decisions/](../../worklogs/decisions/) |
| AI 协作流程 | [ai-workflow_AI协作开发流程/](../../docs/conventions/ai-workflow_AI协作开发流程/) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-06-07 | v1.0 | 初版（整合 9 根目录 skill + CLAUDE.md 红线 + 5 层洋葱 + BDD+TDD 流程 + STATUS/roadmap/PRD 协作约定 + 飞书沉淀协议 + ADR 触发条件 + 12 大踩坑 + 任务清单速查）|
