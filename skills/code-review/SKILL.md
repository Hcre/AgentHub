---
name: code-review
description: Review code changes against AgentHub rules. Use before PR submission or when reviewing others' code.
---

# code-review: 代码审查

## 适用时机

- PR 提交前自查
- 审查同伴代码
- 发现可疑代码时对照红线检查

## 检查维度

### 1. 架构红线 (conventions/01-architecture_架构设计规范.md §一)

| 编号 | 检查项 | 方法 |
|------|--------|------|
| AR-01 | 5层依赖倒置 | L2 不 import L1/L3/L4/L5 |
| AR-02 | 新 Agent 只加 Adapter | 新增 Agent 系统 → `infrastructure/llm/` 下新文件 |
| AR-03 | Harness 不含 LLM | 检查 `domain/task_engine/` 无 LLM 调用 |
| AR-04 | Agent 不直接通信 | 必须通过 Blackboard / Coordinator |
| AR-05 | Task Engine 事件溯源 | 不直接修改 status，走 task_events |
| AR-06 | Agent 系统与模型解耦 | 无硬编码 system→model 映射 |

### 2. 代码红线 (conventions/02-coding_代码编写规范.md §一)

**Python:**
- [ ] CR-01: 无 `print()`
- [ ] CR-02: 无裸 SQL
- [ ] CR-03: DB 变更走 Alembic
- [ ] CR-04: API 端点/外部调用有异常处理
- [ ] CR-05: 所有输入走 Pydantic
- [ ] CR-06: 外部调用有超时
- [ ] CR-12: 无同步阻塞在 async 上下文

**TypeScript:**
- [ ] CR-07: `tsc --noEmit` 零错误
- [ ] CR-08: render 中无 async
- [ ] CR-09: 组件超过 200 行考虑拆分

**通用:**
- [ ] CR-10: 无硬编码密钥
- [ ] CR-11: 无 `print()`/`console.log()` 生产路径

### 3. 流程红线 (conventions/99-process-rules_流程红线全集.md)

- [ ] PR-02: 分支命名符合 `feature/<domain>/<desc>`
- [ ] PR-03: Commit message 符合 Conventional Commits
- [ ] PR-04: Agent 写文件经审批流
- [ ] PR-07: `verify.bat` 全通过
- [ ] PR-08: roadmap 已更新
- [ ] PR-09: SPEC 与代码同步

---

## 执行

```bash
# 自动检查
scripts\verify.bat
python scripts/check_branch.py
python scripts/check_worklog.py
```

不通过 = 不能合并。
