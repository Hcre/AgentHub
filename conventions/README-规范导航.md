# 开发规范 — AgentHub

> **👤 人类快速入口** | AI Agent 请读 `CLAUDE-规范导航.md` 与项目根 `CLAUDE.md`。
> 版本: v3.0 | 更新: 2026-05-28

9 份规范（6 主 + 1 双图谱 + 2 附录）都是 [ai-workflow 协作流程](ai-workflow_AI协作开发流程/) 的**细化**——每份把流程里一句话带过的环节展开成可执行标准（红线 + 自动检测 + 落地配置）。先懂流程，再按环节查规范。

---

## 快速索引

| # | 规范 | 细化的流程环节 | 何时读 |
|---|------|---------------|--------|
| 01 | [架构设计](01-architecture_架构设计规范.md) | 第一步·技术选型与架构设计 | 写计划 / 设计前 |
| 02 | [代码编写](02-coding_代码编写规范.md) | 第二步 §2.1 实现 + §2.3 审查 | 写任何代码前 |
| 03 | [Git 协作](03-git_Git协作规范.md) | 第二步 §2.6 Git 提交 | 提交 / 提 PR 前 |
| 04 | [API 设计](04-api_API设计规范.md) | 第二步 §2.1 实现（接口）| 设计 API 前 |
| 05 | [测试](05-testing_测试规范.md) | 第二步 §2.1 TDD + §2.2 可观测验证 | 写测试前 |
| 06 | [文档](06-documentation_文档规范.md) | §2.5 更新记录 + 07-汇报 | 写文档 / 汇报前 |
| 08 | [代码理解与图谱](08-code-understanding_代码理解与图谱规范.md) | 第二步 §2.9 工具链增强 | 仅中大型（> 10 模块） |
| 99 | [边界矩阵附录](99-boundaries_边界矩阵.md) | 写权限 / 审批逻辑前 | AgentHub 特有 |
| 99 | [流程红线全集附录](99-process-rules_流程红线全集.md) | 完整 PR-01~09 | 03 Git 摘要的扩展 |

> 每份规范开头都标注「细化自哪一步」和档位裁剪。AgentHub 是标准/团队档位，全规范都守。

---

## 红线速查（AgentHub 版）

违反任一条 = **方案打回 / 审查不通过**。完整列表见各规范 §一「红线」。

### 🏗️ 架构（01）— AR-01 ~ AR-06
- **AR-01** 5 层洋葱单向依赖（L5→L4→L3→L2←L1），Domain 不依赖框架
- **AR-02** 新 Agent 系统只加 Adapter，禁改 `backend/app/domain/`
- **AR-03** Harness 不含 LLM 调用
- **AR-04** Agent 间不直接通信（走 Blackboard / Coordinator）
- **AR-05** Task 状态变更走 FSM + 事件溯源 + 幂等键
- **AR-06** Agent system 与 model 解耦
（AR-01/02 由 `import-linter` 自动拦截，AR-03~06 列入 CR 清单）

### 💻 代码（02）— CR-01 ~ CR-12
Python：禁 print / SQL 参数化 / Alembic 走 migration / try-except + 日志 / Pydantic v2 / 外部 API 超时 + 重试 + 熔断 / async 上下文禁同步阻塞
TypeScript：strict 零错误禁 `any` / 禁 render 中 async / 组件 < 200 行（warn）
通用：禁硬编码密钥 / 禁遗留调试代码
（CR-01/10/11 由 ruff + gitleaks pre-commit 自动拦）

### 🔄 Git（03）— 摘要 PR-02/03/06/07
- 分支 `feature/<domain>/<desc>`（scope: chat/orchestration/toolchain/frontend/backend/docs/ci/deps）
- 禁直推 main · Conventional Commits · ≥ 1 Approve（跨域 2 人）
- 提交前跑 `verify.{bat,sh}`
（commitlint + 分支保护 + `scripts/check_branch.py` 强制）

### 🌐 API（04）— AP-01 ~ AP-07
- 名词复数 + kebab-case，无动词 · 错误响应 `{error:{code,message}}` · 默认 JWT 认证
- Pydantic v2 校验输入 · URL 路径版本 `/api/v1/` · 向后兼容
- WS 消息必含 `type` + `payload` + `request_id`

### 🧪 测试（05）— T-01 ~ T-06
- 测试独立 · 只 Mock 外部边界（真实 PG + Redis Testcontainers）· 覆盖正常+边界+异常 · 无 flaky
- Adapter 必测 成功/限流/超时/key失效/流式中断 · FSM 必测 合法/非法/幂等/边界
- 覆盖率：后端 ≥ 80%（行）+ 70%（分支），前端 ≥ 70%

### 📄 文档（06）— D-01 ~ D-12
- 根 README + CLAUDE 必存 · 文档随码同 PR · 公共 API 有 docstring · 注释与代码一致
- 命名 `{English}_{中文}.md` · explore EXP-NN_ / 个人子目录 · archive `DEPRECATED_` 前缀
- worklog `YYYY-MM-DD_*.md` · 禁版本后缀（`_v2/_final/_old`）· docs/ 树（除 reports/）禁 .html
- CLAUDE 引用必可解析 · pre-commit + pre-push 钩子必装
（D-05~12 由 `scripts/check_docs.py` 自动拦）

### 🚦 流程（99-process-rules）— PR-01 ~ PR-09
- PR-01 接口先行（2 人 Review 后才能实现）· PR-04 Agent 写文件必经审批 · PR-05 每里程碑全员集成测试
- PR-08 改代码后更新 `docs/plan/开发清单_roadmap.md` 验收状态 · PR-09 SPEC 和代码同步

### 🛡️ 边界（99-boundaries）
Agent 操作权限矩阵：Always（自动）/ Ask First（需审批）/ Never（硬禁止），含 0 节审批模式（正常 vs 执行模式）。

---

## 常用规约一览

- **分支**：`feature/<domain>/<desc>`，禁直 push main
- **提交**：Conventional Commits（`feat:`/`fix:`/`refactor:`/`docs:`/`test:`/`chore:`）
- **验证**：每次 commit 前 `verify.bat` 或手动 ruff / tsc / eslint / pytest
- **日志**：每次工作后 `worklogs/{你}/YYYY-MM-DD_<desc>.md`，更新 `STATUS.md`
- **文档**：命名 `{English}_{中文}.md`，pre-push 钩子自动检查
- **依赖安装**：克隆后首装 `pre-commit install --hook-type pre-push && pre-commit install`
