---
name: git-workflow
description: Git 分支工作流 — 确保在 feature 分支开发，同步 main 差异，合并前 diff 审查。触发：开始开发前、发现 main 落后、准备合并 feature→main 时。
---

# git-workflow: Git 分支工作流

> 核心原则：**不在 main 上开发，不猜测差异，合并前必须审查。**

## 适用时机

- 开始任何开发工作前
- 准备 push 前
- 发现 origin/main 有新提交时
- 准备将 feature 分支合并到 main 时
- 队友说「帮我看看这个分支能不能合」

## 前置检查

执行任何操作前先确认：

```bash
git fetch origin
```

## 流程 A：开始开发前

### A1. 检查当前分支

```bash
git branch --show-current
```

| 当前分支 | 操作 |
|----------|------|
| `main` | **禁止在 main 上开发。** 如果是文档类小改动且确认无冲突 → 可以继续。如果是代码改动 → 必须切 feature 分支 |
| `feature/<domain>/<desc>` | 继续 A2 |
| 其他 | 确认是否规范命名 |

### A2. 检查 main 是否落后

```bash
git rev-list --count main..origin/main
```

| 结果 | 操作 |
|------|------|
| 0 | main 已是最新，跳到 A4 |
| >0 | main 落后，执行 A3 同步 |

### A3. 同步 main（有差异时）

```bash
git diff main..origin/main --stat
```

根据 diff 范围判断：

```
仅文档变更（docs/ spec/ *.md）    → 安全，直接 git pull
代码变更 + 无冲突风险             → 安全，直接 git pull
代码变更 + 涉及当前分支改动文件   → 需要审查，执行 A3.1
```

#### A3.1 差异审查

逐文件展示 `git diff main..origin/main` 的关键变更，按以下分类处理：

| 分类 | 判断标准 | 处理 |
|------|----------|------|
| **安全** | 新增文件、格式化、注释、非重叠函数 | 直接接受 |
| **模糊** | 同一函数被修改、逻辑变更、删除代码、配置变更 | **必须询问用户**，给出 diff 摘要和推荐操作 |

**禁止猜测。** 任何不确定的差异，展示给用户并等待确认。

### A4. 同步 main 到当前分支

```bash
git pull origin main           # 如果当前分支尚未 push
# 或
git merge origin/main          # 如果当前分支已有提交
```

---

## 流程 B：准备合并 feature → main

### B1. 确保 main 最新

```bash
git fetch origin
git checkout main
git pull origin main
```

### B2. 生成完整差异

```bash
git diff main...feature/<domain>/<desc> --stat
```

### B3. 逐文件审查

对每个变更文件分类：

| 分类 | 处理 |
|------|------|
| **文档** (docs/ spec/ *.md) | 安全，直接合 |
| **新增文件** (新 feature、新 test) | 安全检查：是否有测试、是否遵循项目规范 |
| **修改已有代码** | 重点审查：是否引入回归风险、是否影响其他域 |
| **删除文件/代码** | **必须确认**：展示给用户 |
| **配置变更** (.env, config.py, src/docker/) | **必须确认**：可能影响部署 |

### B4. 合并

```bash
git checkout main
git merge feature/<domain>/<desc>
```

如果无冲突：

```bash
git push origin main
```

如果有冲突：

```
展示冲突文件 + 冲突内容 → 询问用户如何解决 → 手工解决 → 提交 merge commit → push
```

### B5. 合并后清理

```bash
git branch -d feature/<domain>/<desc>   # 删除本地分支（可选）
git push origin --delete feature/<domain>/<desc>   # 删除远程分支（可选）
```

---

## 流程 C：队友推了 main，我需要同步

### C1. Fetch + 检测

```bash
git fetch origin
B=$(git rev-list --count main..origin/main)
echo "main 落后 $B 个提交"
```

### C2. 查看差异

```bash
git log main..origin/main --oneline
git diff main..origin/main --stat
```

### C3. 分类处理

同 A3.1 的审查逻辑：安全直接合，模糊必询问。

### C4. 同步

```bash
git pull origin main
```

如果当前在 feature 分支：

```bash
git checkout <feature-branch>
git merge main   # 将最新 main 合并到 feature
```

---

## 安全 / 模糊 判断速查

### 自动归类为「安全」

- 文件仅存在于 origin/main（新增文件，当前分支无冲突）
- 变更仅涉及注释、空行、格式化
- `docs/` `spec/` `README.md` `CLAUDE.md` 的独立段落变更
- `worklogs/` 目录下的任何变更

### 必须归类为「模糊」→ 询问用户

- 同一行/同一函数在当前分支和 origin/main 都被修改过
- `.env` `.env.example` `docker-compose.yml` `config.py` 的变更
- `alembic/versions/` 下的 migration 文件
- `package.json` `pyproject.toml` 的依赖变更
- 删除任何文件（即使是文档）
- 涉及 `app/api/` `app/domain/` 等核心业务逻辑的变更

### 询问格式

```
## 差异审查 — 需要你确认

### 文件: src/backend/app/domain/entities/session.py
- origin/main 新增了 `status` 字段
- 你的分支也修改了 `Session` 类的 `__post_init__`
- 风险: 字段定义位置可能冲突

**推荐**: 先合 main，再在你的分支上解决冲突

### 文件: docker-compose.yml
- origin/main 新增了 `CELERY_WORKER` 服务

**推荐**: 直接接受（你的分支未修改此文件）

---
以上 2 处差异，确认后我将执行:
1. git pull origin main
2. 如有冲突 → 手工解决
```

---

## 关键规则

1. **禁止在 main 上直接开发代码。** 文档小改除外。
2. **禁止猜测 diff 意图。** 不确定就展示给用户。
3. **合并前必须走 B3 审查。** 不能跳过。
4. **每次操作后验证。** merge 后跑 `git status`，push 后确认 remote 更新。
5. **队友的 worklog 永远直接接受。** 不审查 worklogs/ 下的变更。
6. **日志按天拆分。** 每天写新文件 `YYYY-MM-DD_<简短描述>.md`，不要追加到前一天日志里。
7. **Push 后必须询问用户是否 PR 到 main。** 给出命令或链接。
