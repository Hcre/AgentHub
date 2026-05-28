# 工作日志：初始化 AI 协作体系 + Docker 环境部署

- **谁**: 黎
- **日期**: 2026-05-22
- **分支**: ai-collab-setup
- **关联 Spec**: `spec/AgentHub_SPEC_项目主规格.md`

## 目标

建立项目仓库的 AI 协作规范体系，部署 MVP 脚手架到本地 Docker 环境。

## 产出

### 上午：协作文档体系
- [x] 将外部 `spec/` 整合到 repo 内，建立 `docs/`(人读) + `spec/`(AI读) 双轨
- [x] 精简三大规则文件：arch-rules 8→6, code-rules 16→12, process-rules 9→9
- [x] 重写 `.agenthub/CLAUDE.md` 作为 AI 统一入口
- [x] 建立 `worklogs/` 目录 + `template.md` + `STATUS.md`（黎/董/袁）
- [x] 复制 `skill/spec-driven-development` 到 `skills/`
- [x] 删除外部 `D:/AgentHub/spec/`

### 下午：自动化验证体系
- [x] 增强 ruff（T20 禁 print + ASYNC 禁同步阻塞 + SIM + RUF）→ `backend/pyproject.toml`
- [x] 新增 ESLint 配置（no-console + max-lines 提示）→ `frontend/.eslintrc.json`
- [x] 新增 `.pre-commit-config.yaml`（ruff / eslint / tsc / 分支命名检查）
- [x] 新增 `scripts/verify.sh` + `scripts/verify.bat`（一键跑全部检查）
- [x] 新增 `scripts/check_branch.py`（PR-02 分支命名检查）

### 晚上：Docker 环境部署
- [x] 安装 Docker Desktop → 引擎启动失败，改在 WSL Ubuntu 里装 Docker Engine 29.5.2
- [x] 修复 WSL2：`hypervisorlaunchtype` 设为 `auto`，装 Ubuntu 26.04
- [x] Ubuntu 迁移到 E 盘（`E:\wsl\ubuntu`）
- [x] 配置 Docker 镜像加速器（`https://docker.1ms.run`）
- [x] `docker compose up --build` 成功，5 个容器运行
- [x] 验证：`localhost:8000/health` → 200, `localhost:5173` → 200

### Rules → Script 映射

| 规则 | 执行工具 | 位置 |
|------|---------|------|
| CR-01 禁 print | ruff T20 | `backend/pyproject.toml` |
| CR-02 禁裸 SQL | CR 手工 | — |
| CR-03 必须 Alembic | CR 手工 | — |
| CR-04 API/外部调用有异常处理 | CR 手工 | — |
| CR-05 Pydantic 校验输入 | CR 手工 | — |
| CR-06 外部调用超时+重试 | CR 手工 | — |
| CR-07 TS strict | `tsc --noEmit` | `.pre-commit-config.yaml` |
| CR-08 render 禁 async | eslint | `frontend/.eslintrc.json` |
| CR-09 组件>200行建议拆分 | eslint max-lines | `frontend/.eslintrc.json` |
| CR-10 禁硬编码密钥 | pre-commit (future: gitleaks) | — |
| CR-11 禁遗留调试代码 | ruff T20 / eslint no-console | `pyproject.toml` + `.eslintrc.json` |
| CR-12 禁同步阻塞 async | ruff ASYNC | `backend/pyproject.toml` |
| AR-01 依赖倒置 | 待配 import-linter | — |
| PR-02 分支命名 | `scripts/check_branch.py` | `.pre-commit-config.yaml` |
| PR-07 提交前验证 | `scripts/verify.sh` / `.bat` | `scripts/` |

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| docs/ vs spec/ 分层 | docs 给人读叙事文，spec 给 AI 读结构化数据 | 新文档需判断归属 |
| 规则 33→25 条 | 删重复（AR-07/CR-08/CR-16）、过严（CR-12删）、非协作（PR-04删） | 减少无意义告警 |
| SubAgent 不定死 | 三人各自组织，灵活性优先 | 等出现混乱再约定 |
| STATUS.md 各自维护行 | 冲突概率极低 | 需每人遵守 |
| Docker 在 WSL 内而非 Desktop | Desktop 引擎多次启动失败，WSL 内直接装更稳 | 每次启动 WSL 后需 `sudo service docker start` |

## 未完成 / 阻塞

- [ ] ESLint 需 `cd frontend && npm install` 安装依赖 → 待配自动化
- [ ] pre-commit 钩子需 `pre-commit install` 激活 → 三台机器各自执行
- [ ] import-linter 未配（AR-01 依赖方向自动检查）
- [ ] 核心 Skills 未创建（feat-start / feat-complete / code-review / deploy）
- [ ] STATUS.md 中董和袁未填写

## 给下一位的交接

> Docker 部署成功，`localhost:8000` 和 `localhost:5173` 可访问。下一步：创建核心 Skills，然后进入 M2 单聊 MVP 开发（WebSocket + 流式 + Chat UI）。
> 
> 每次任务完成后：1) 更新个人 worklog 2) 更新 STATUS.md 自己行 3) 如果完成 roadmap 任务，更新 `spec/roadmap_开发路线图.md` 4) Commit + Push
