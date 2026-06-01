# 规范导航（AI 版） — AgentHub

> **⚠️ 仅供 AI Agent**。人类读 `README.md`。
> 用途：开工前先按「任务→规范」定位该加载哪几篇，再读对应篇的 §一红线 + §二落地配置。不要一次读完 9 篇。

---

## 1. 规范 = 流程的细化

`docs/conventions/` 各篇不是孤立文档，是 [ai-workflow](ai-workflow_AI协作开发流程/) 各步骤的**细化**。到流程的哪一步，就读对应规范：

| 流程步骤 | 读哪篇 | 这篇定义「那一步具体怎么做」 |
|---------|--------|--------------------------|
| 第一步·技术选型与架构 | [01 架构](01-architecture_架构设计规范.md) | 5 层洋葱 / 依赖倒置 / Adapter 模式 / FSM / 配置 |
| 第二步 §2.1 实现（写接口）| [04 API](04-api_API设计规范.md) | REST + WS 设计 / 错误响应 / 输入校验 |
| 第二步 §2.1 实现（写代码）| [02 代码](02-coding_代码编写规范.md) | 命名 / 结构 / 错误处理 / 安全 |
| 第二步 §2.1 TDD / §2.2 验证 | [05 测试](05-testing_测试规范.md) | TDD 节奏 / 覆盖率 / Mock 边界 / Adapter+FSM 必测 |
| 第二步 §2.3 审查 diff | [02 §五检查清单](02-coding_代码编写规范.md) | 审查清单 = 该篇检查清单 |
| 第二步 §2.6 提交 | [03 Git](03-git_Git协作规范.md) | 分支 / 提交格式 / PR / 合并 / 多人协作 |
| §2.5 记录 + 07-汇报 | [06 文档](06-documentation_文档规范.md) | docs/ 命名 / explore / ADR / worklog |
| Agent 操作权限 / 边界 | [99 边界矩阵](99-boundaries_边界矩阵.md) | Always / Ask First / Never |
| 流程合规校验 | [99 流程红线](99-process-rules_流程红线全集.md) | PR-01~09 完整流程红线 |
| 中大型项目工具 | [08 图谱](08-code-understanding_代码理解与图谱规范.md) | CodeGraph + Understand-Anything 双图谱 |

> AgentHub 是标准/团队档位，全规范都守。档位定义见 [第一步 §1.0](ai-workflow_AI协作开发流程/03-第一步_编写计划.md)。

---

## 2. AgentHub 红线总表（违反 = 打回，写代码/审查时逐条核）

### 架构红线（AR-01 ~ AR-06，见 01 §一）
| # | 红线 | 自动检测 |
|---|------|---------|
| AR-01 | 5 层洋葱单向依赖；Domain 不依赖框架/ORM | `import-linter` layers |
| AR-02 | 新 Agent 系统只加 Adapter，禁改 `src/backend/app/domain/` | `import-linter` forbidden + CR |
| AR-03 | Harness 不含 LLM 调用 | grep + CR |
| AR-04 | Agent 间不直接通信（走 Blackboard / Coordinator） | CR |
| AR-05 | Task 状态变更走 FSM + 事件溯源 + 幂等键 | 单测 + CR |
| AR-06 | Agent system 与 model 解耦 | grep 配置 + CR |

### 代码红线（CR-01 ~ CR-12，见 02 §一）
| # | 红线 | 自动检测 |
|---|------|---------|
| CR-01 | 禁裸 `print()` | ruff `T20` |
| CR-02 | SQL 必须参数化 | ruff `S608` |
| CR-03 | 数据库变更走 Alembic | grep `ALTER TABLE` |
| CR-04 | API/外部/DB 必须 try/except + 日志 | CR |
| CR-05 | API 输入用 Pydantic v2 model | CR |
| CR-06 | 外部 API 有 timeout + retry + 熔断 | CR |
| CR-07 | TS strict + 禁 `any` | tsc + eslint |
| CR-08 | 禁 React render 中 await | eslint react-hooks |
| CR-09 | 组件 < 200 行（warn） | eslint `max-lines` |
| CR-10 | 禁硬编码密钥/Token | ruff `S105-7` + gitleaks |
| CR-11 | 禁遗留 print/console.log/注释代码块 | ruff `ERA001` |
| CR-12 | async 上下文禁同步阻塞 | ruff `ASYNC` |

### 流程红线（PR-01 ~ PR-09，见 99-process-rules 全集 / 03 Git 摘要）
| # | 红线 | 自动检测 |
|---|------|---------|
| PR-01 | API 接口先冻结再实现；变更需 2 人 Review | 流程规则 + CR |
| PR-02 | 分支 `feature/<domain>/<desc>`；禁直推 main | `check_branch.py` + GitHub 分支保护 |
| PR-03 | Conventional Commits | commitlint |
| PR-04 | Agent 写文件必经审批 | 边界矩阵 + 审批 UI |
| PR-05 | 每里程碑结束全员集成测试 | M 验收门禁 |
| PR-06 | PR ≥ 1 Approve；跨域接口变更 2 人 | GitHub 分支保护 |
| PR-07 | 提交前跑 `verify.{bat,sh}` | pre-commit + CI |
| PR-08 | 改代码后更新 `docs/plan/开发清单_roadmap.md` 验收状态 | CR |
| PR-09 | SPEC 和代码同步（架构 / 数据 / API / 里程碑） | CR |

### API 红线（AP-01 ~ AP-07，见 04 §一）
| # | 红线 |
|---|------|
| AP-01 | 名词复数 + kebab-case URL，无动词 |
| AP-02 | 错误响应统一 `{error: {code, message}}` |
| AP-03 | 默认 JWT 认证 |
| AP-04 | Pydantic v2 校验输入 |
| AP-05 | URL 路径版本号 `/api/v1/` |
| AP-06 | 向后兼容（不删/不改字段） |
| AP-07 | WS 消息必含 `type` + `payload` + `request_id` |

### 测试红线（T-01 ~ T-06，见 05 §一）
| # | 红线 |
|---|------|
| T-01 | 测试独立 |
| T-02 | 只 Mock 外部边界（真实 PG + Redis Testcontainers） |
| T-03 | 覆盖正常 + 边界 + 异常 |
| T-04 | 无 flaky |
| T-05 | Adapter 必测 成功/限流/超时/key失效/流式中断 |
| T-06 | FSM 必测 合法/非法/幂等/边界 |

### 文档红线（D-01 ~ D-12，见 06 §一）
全部对齐 `scripts/check_docs.py` 自动检测，详见 06。

---

## 3. 单一权威 / 去重映射（改动时别复制到别处）

| 主题 | 唯一权威 | 别处只引用 |
|------|----------|-----------|
| AR-01~06 架构红线 | 01 §一 | CLAUDE.md 速查表只引用 |
| CR-01~12 代码红线 | 02 §一 | 同上 |
| PR-01~09 流程红线全集 | 99-process-rules | 03 Git 摘 PR-02/03/06/07 |
| AP-01~07 API 红线 | 04 §一 | — |
| T-01~06 测试红线 | 05 §一 | — |
| D-01~12 文档红线 | 06 §一 | — |
| Agent 权限矩阵 | 99-boundaries | 01/04 仅引用 |
| 密钥 / 代码级安全 | 02 CR-10 | 01 配置管理引用 |
| 跨层调用 / 循环依赖 / 分层 | 01 | 08 提供大型项目自动检测 |
| 调用图 / 影响分析 / 代码地图 | 08（全部收拢） | 01/02/05/06 各留一句指向 08 |
| 错误响应格式 | 04 AP-02 | 02 错误处理引用 |
| Conventional Commits | 03 | — |
| 文档模板正文 | `docs/templates/` | 06 只链接不重抄 |
| 完整 API endpoint 清单 | `docs/specs/04-commands_命令接口.md` | 04 只定原则 |
| 完整测试用例清单 | `docs/specs/05-testing-strategy_测试策略.md` | 05 只定原则 |
| 适配器接口契约 | `docs/specs/04c-adapter-interface_适配器接口规范.md` | 01/04 引用 |

---

## 4. 任务 → 规范 定位速查

| 用户说 | 必读 | 选读 |
|--------|------|------|
| "加新功能 X" | 04 API（接口冻结）→ 02 代码 → 05 测试 → 03 Git | 01 架构（涉新模块） |
| "改架构 / 加新 Adapter" | 01 架构（AR-02 流程）→ 09 ADR 模板 | 04 API（若改外部接口） |
| "改数据库" | 01（AR-05 FSM）+ 02（CR-03 Alembic）+ `docs/specs/03-data-model_数据模型.md` | 05 测试（Migration 正反） |
| "改 API endpoint" | 04 + PR-01（接口先行 2 人 Review） + PR-09（SPEC 同步） | — |
| "写测试" | 05 测试 | 02 §四（异常路径） |
| "提 PR / 合并" | 03 Git + 99-process-rules（PR-06/07） | — |
| "新 Agent 系统" | 01 §4.2（AR-02 流程）+ `docs/specs/04c-adapter-interface_适配器接口规范.md` | — |
| "写文档 / 移动文件" | 06 文档 + [meta/FILE_GRAPH.md](../../meta/FILE_GRAPH.md) | — |
| "Agent 操作权限" | 99 边界矩阵 | — |
| "调用图 / 影响分析（M3+ 才用）" | 08 | — |

---

## 5. 改规范时的同步清单

1. 改 `docs/conventions/NN-*.md` → 同步 `docs/specs/NN-*.md` 规格（若有对应）
2. 红线增删 → 同步本文件 §2 + `README.md` 红线速查
3. 改 §二落地配置 → 同步实际配置文件（`pyproject.toml` / `.pre-commit-config.yaml` / `eslint.config.js`）
4. 改文档命名规则 → 同步 `scripts/check_docs.py`
5. 改分支命名规则 → 同步 `scripts/check_branch.py`
6. 改 worklog 路径 → 同步 `scripts/check_worklog.py` 和 `scripts/check_docs.py`
7. 汇报：更新 `worklogs/{你的名字}/YYYY-MM-DD_*.md` + `STATUS.md`（见 [CLAUDE.md](../../CLAUDE.md) 工作流程）

> 各篇正文结构统一：§一红线（配检测）→ §二落地配置 → §三决策表 → 反模式 → 检查清单 → 关联 → 更新记录。
