# ADR-0012: Mavis owner 委派决策 — BDD 场景全量沉淀（PRD 6 大核心功能 + roadmap §8 P0/P1/P2 缺口）

- **状态**: Accepted
- **日期**: 2026-06-07
- **决策者**: Mavis (owner, per ADR-0008 自主决策授权)
- **关联 Spec**: [docs/specs/04-commands_命令接口.md §六 BDD 验收场景](../docs/specs/04-commands_命令接口.md) · [docs/conventions/05-testing_测试规范.md §二点五 BDD+TDD](../docs/conventions/05-testing_测试规范.md) · [docs/plan/开发清单_roadmap.md §8 P0/P1/P2 任务表](../docs/plan/开发清单_roadmap.md) · [docs/plan/背景.md PRD 6 大核心功能](../docs/plan/背景.md)
- **关联 BDD**: §六 16+ 场景（B-1-P0-S01~S05, B-1-P0-04, B-2-P2-F01, B-3-P0-A01~A02, B-4-P2-D01~D03, B-5-P2-DP01, B-6-P2-M01, B-6-P2-V01, B-5.3-P1-2, B-5.4-P1-3, B-7-P2-FD01）
- **关联 Skill**: [skills/agenthub-dev/SKILL.md](../skills/agenthub-dev/SKILL.md) v1.0

## 背景

`plan_ba86c4d0`（Mavis owner 14:26 session）委派 docs-writer 任务：
> 基于 STATUS.md + roadmap §8 + PRD 背景文件，给 status 内所有 P0+P1+P2 task 写 BDD spec。

具体范围（per task instructions）：
1. `docs/specs/04-commands_命令接口.md` 加 Given/When/Then 段覆盖 12 类场景（P0-4 Pin session 校验 / P1-2 Token 监控 / P1-3 CLI PATH 扫描 / 对话列表搜索/置顶 / 消息操作回复/引用 / 文档渲染 / 全屏预览 / Monaco 编辑器 / 部署卡 / v6 录制脚本 / 移动端 H5 / 失败降级）
2. `skills/agenthub-dev/SKILL.md`（AgentHub 开发最佳实践）
3. `docs/conventions/05-testing_测试规范.md` 补 BDD+TDD 流程段
4. ADR（如需，记录 Mavis owner 委派决策）
5. worklogs/mavis/2026-06-07_*.md session worklog

**当前状态**（per STATUS.md 2026-06-07 14:26）：
- M5 5.5 SPEC 沉淀 ⬜ 待办（roadmap §六 5.5 状态 ⬜/⚠️）
- 课题「AI 协作能力 30%」考察点 = "沉淀出和 ai 协作的 Spec、skill、rules 等协作规范"（per 背景.md line 62-64）
- 已知 6 gap（STATUS.md line 30-34 + 104-130）：
  - E 视觉 S5 inbox 3 重 gap（M4 TODO 标）
  - S3 私聊 UI 不可达（downscope）
  - **P0-4 Pin API 无 session 所有权校验**（probe 2 FAIL，**需 backend 修复**）
  - Docker backend image 滞后
  - 视频 v4 wallpaper 44.9% 残留
  - 6 个 ⚠️ 部分 + 7 个 ❌ 未做

**核心问题**：
- 后端 P 任务收束（如 P0-4 Pin API session 校验）需要**契约冻结**——没有 BDD 就没有验收标准
- frontend P 任务收束（对话列表搜索/置顶、文档渲染、全屏预览、Monaco、部署卡、移动端 H5）需要**接口 + UI 验收描述**
- 整体 P 任务（P0-4~6 + P1-1~4 + P2 缺口）= **~25 个任务**，对应 ~35-50 个 BDD 场景
- 当前 04-commands §六 **空缺**——PR-01 接口冻结只覆盖了 §2.6（MCP 8 端点），其他 P 任务无 BDD

## 决策

**Mavis owner 决定**（per ADR-0008 自主决策授权）：

### 决策 1：04-commands §六 全量 BDD 沉淀

**新增 §六 BDD 验收场景**，覆盖 PRD 6 大核心功能 + roadmap §8 P0-4 / P1-2 / P1-3 + 11 P2 缺口：

| § | 内容 | 场景数 | 状态 |
|---|------|--------|------|
| 6.1 | IM 聊天式交互（搜索/置顶/回复/引用/重新生成/Pin 所有权）| 6 场景 | 全冻结 |
| 6.2 | Orchestrator 失败降级 | 1 场景 | 冻结 |
| 6.3 | 多 Agent 接入（对话式 + 表单式自建）| 2 场景 | 冻结 |
| 6.4 | 产物预览（文档渲染 / 全屏预览 / Monaco）| 3 场景 | 冻结 |
| 6.5 | 多端（移动端 H5 / v6 录制脚本）| 2 场景 | 冻结 |
| 6.6 | Token 消耗监控（P1-2）| 1 场景 | 冻结 |
| 6.7 | CLI PATH 扫描（P1-3）| 1 场景 | 冻结 |
| 6.8 | 失败降级矩阵 | 1 场景 | 冻结 |
| **合计** | | **17 场景** | |

**每个 BDD 场景含**：
- 场景 ID + 对应任务 + API 端点
- Given（前置：数据 / 鉴权 / 状态）
- When-1/2/3（合法 / 非法 / 边界）
- Then-1/2/3（HTTP 状态 / 响应体 / DB 副作用 / WS 推送）
- 错误码覆盖（401/403/404/422 至少 1）
- UI 验收（Playwright E2E 描述关键 DOM 断言）

**新增 §七 BDD↔任务映射速查表**——给实现者：「我接 P 任务 X，先在 §六 找 BDD Y」。

**新增 §八 关联文档 + 更新记录**。

### 决策 2：skills/agenthub-dev/SKILL.md v1.0

**新增 Skill**（根目录 skills/）：

- **整合范围**：9 根目录 skill（feat-start / feat-complete / git-workflow / code-review / spec-driven-development / test-claude-adapter / doc-sync / deploy / frontend-style-edit）+ CLAUDE.md 红线 + 5 层洋葱 + BDD+TDD 流程 + STATUS/roadmap/PRD 协作约定 + 飞书沉淀协议
- **15 章**：
  0. 动手前 5 问
  1. 开发链路 7 步
  2. 5 层洋葱架构
  3. 5 大工程红线
  4. API 7 红线
  5. 文档 12 红线
  6. 飞书文档沉淀协议
  7. ADR 触发条件
  8. commit 风格（Conventional Commits + scope-enum）
  9. E2E + 集成验证协议
  10. demo 录制协议
  11. STATUS.md 协作约定
  12. 12 大踩坑
  13. 任务清单速查
  14. 检查清单
  15. 关联文档

**使用时机**：任何 AgentHub 开发（写后端 / 前端 / spec / test / commit / push）都先 load 这份 Skill，再开始动手。

### 决策 3：05-testing 规范 v3.1（BDD+TDD 双循环）

**新增 §二点五 BDD+TDD 双循环流程**，9 子节：
- 2.5.1 BDD 场景权威源
- 2.5.2 BDD 三件套（Given/When/Then）
- 2.5.3 BDD → TDD 翻译（AAA + 命名）
- 2.5.4 BDD+TDD 双循环工作流（3 阶段）
- 2.5.5 BDD vs TDD vs E2E 分工
- 2.5.6 BDD+TDD 反模式
- 2.5.7 BDD+TDD 工具链
- 2.5.8 BDD+TDD 检查清单
- 2.5.9 BDD+TDD 落地里程碑（M5 收束 / M6 答辩 / MVP 2.0 3 档目标）

### 决策 4：commit 拆分（docs 单独 commit）

**5 commit 拆分**（per CLAUDE.md 行为准则 + 03-git PR-03）：

1. `docs(specs): 增 BDD §六 覆盖 P0-4/P1-2/P1-3 + 11 P2 缺口`（04-commands）
2. `feat(skills): agenthub-dev v1.0 整合 9 根目录 skill + 红线`（新 skill）
3. `docs(testing): 增 §二点五 BDD+TDD 双循环流程 v3.1`（05-testing）
4. `docs(adr): 0012 mavis owner 委派 BDD 沉淀决策`
5. `docs(worklog+status): 14:26 session 落档 + roadmap §8 P 状态`

**push 策略**：user 偏好（2026-06-07 落档 memory）—— **直接 push main**，不走 PR 流程。

## 影响

### 正面

- **M5 5.5 SPEC/Skill/Rules 沉淀** ⬜/⚠️ → **✅ 完成**（roadmap §六 5.5 状态更新）
- **课题 30% AI 协作能力**考察点「Spec、skill、rules 等协作规范」有落档产出
- **后端 P 任务开工有契约**：P0-4 Pin session 校验有 B-1-P0-04 + 错误码 `E_MESSAGE_PIN_NOT_OWNER` / `E_MESSAGE_PIN_SESSION_MISMATCH` 锁死
- **前端 P 任务有 UI 验收**：对话列表搜索/置顶、文档渲染、全屏预览、Monaco、移动端 H5 都有 Playwright DOM 断言
- **TDD 翻译有模板**：pytest + vitest AAA 模板 + 命名规范
- **踩坑有规避清单**：12 条「错 → 正确」（S5 inbox 演示 / Win32 SetWindowPos / PS 5.1 管道 / 绝对 feishu URL / CJK 保留字符 / vite dev container HMR / cu 视觉 vs playwright / MCP 路径 / WS 信封）

### 负面 / 后续 TODO

- **17 BDD 场景**只是「**契约冻结**」——实际 TDD 翻译成 pytest + vitest 测试**还要等开工**（不是 docs-writer 范围）
- **P0-4 Pin session 所有权校验** BDD 写了 `B-1-P0-04`（含 403/422 错误码），但**后端实现**仍是 gap #3（probe 2 FAIL）—— 等 backend-developer 接手
- **P1-2 Token 消耗 / P1-3 CLI PATH 扫描** BDD 冻结了，但实现 ⬜ 待办
- **8 P2 缺口**（回复/引用/文档/全屏/Monaco/部署/移动端 H5/失败降级）BDD 冻结，但实现 ❌ 未做
- **AgentHub 风格 v1.0 Skill** 是「**整合 9 个根目录 skill**」的二级索引——未来新加 skill 需同步更新
- **本 ADR 不动 §2.6 MCP 冻结**——MCP 8 端点 PR-01 Review Approve 状态不变

### 后续 roadmap

| 时机 | 任务 | 责任人 |
|------|------|------|
| M5 收束（6/9 答辩前）| TDD 翻译 P0-4 + P1-2 + P1-3 三个 BDD → 单测 | backend-developer + frontend-developer |
| M6 答辩（6/10）| 跑 `scripts/check_docs.py` 0 错 + `scripts/check_worklog.py` 0 错 | docs-writer |
| MVP 2.0（远期）| 50+ BDD 场景 + 300+ 单测 + 12+ E2E + CI gate 全绿 | 全员 |
| 桌面 App（M2 启动后）| 桌面 App 需 6 P3 BDD 补完（per 06-desktop-app §十二 4 Q）| 黎 |

## 替代方案

### 方案 B：BDD 散落到各 spec（不集中 04-commands）

- **内容**：01-architecture / 03-data-model / 04-commands / 05-testing-strategy 各加 BDD 段
- **不选原因**：BDD 跨多个 spec 章节会重复 + 维护成本高 + 实现者「找 BDD」路径长
- **优势**：上下文聚焦

### 方案 C：BDD 写 Gherkin .feature 文件（pytest-bdd / vitest-cucumber）

- **内容**：用 `.feature` 文件 + pytest-bdd 跑 BDD 直接当测试
- **不选原因**：增加学习成本 + Gherkin 中文表达力差 + pytest-bdd 生态成熟度低
- **优势**：Given/When/Then 可执行

### 方案 D：等下一会话再做 BDD 沉淀

- **内容**：本次 session 只写 worklog + STATUS，不动 spec
- **不选原因**：M5 5.5 已 ⚠️/⬜，课题 30% 考察点未满足；且 docs-writer 任务明确要求 12 类场景
- **优势**：本次 session 工作量小

## 关联

- **上游决策**：[ADR-0008 自主决策授权](0008-self-governance-authorization.md)（Mavis owner 有权写 ADR）
- **下游文档**：
  - [04-commands §六 BDD 验收场景](../docs/specs/04-commands_命令接口.md)
  - [05-testing §二点五 BDD+TDD 双循环](../docs/conventions/05-testing_测试规范.md)
  - [skills/agenthub-dev/SKILL.md v1.0](../skills/agenthub-dev/SKILL.md)
- **承接 worklog**：[worklogs/mavis/2026-06-07_BDD全量沉淀+M5-5.5落档.md](2026-06-07_BDD全量沉淀+M5-5.5落档.md)
- **plan_ba86c4d0 board**：[C:\Users\yhn\.mavis\plans\plan_ba86c4d0\board.md]

---

**状态追踪**：
- [x] 2026-06-07 14:30 - 决策起草（per plan_ba86c4d0 委派）
- [x] 2026-06-07 14:35 - 04-commands §六 写完（17 场景冻结）
- [x] 2026-06-07 14:38 - skills/agenthub-dev/SKILL.md v1.0 写完
- [x] 2026-06-07 14:42 - 05-testing v3.1 §二点五 写完
- [x] 2026-06-07 14:45 - ADR-0012 本文档落档
- [ ] 2026-06-07 15:00 - check_docs.py 0 错 + commit 5 拆分 + push main
- [ ] 2026-06-07 15:10 - 给 Mavis owner report commit hash
