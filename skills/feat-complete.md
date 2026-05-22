---
name: feat-complete
description: Complete a feature — run validation, update roadmap, create PR, write worklog. Use when a feature branch is ready to merge.
---

# feat-complete: 功能完成流程

> **一键执行**: `scripts\feat-complete.bat`
> **Linux/WSL**: `bash scripts/feat-complete.sh`

## 适用时机

- 功能分支开发完毕，准备合并
- 所有测试通过，代码符合规范
- 需要提交 PR 并更新项目状态

## 执行步骤

### 1. 跑验证

```bash
# Windows
scripts\verify.bat

# Linux/Mac
bash scripts/verify.sh
```

验证包含：
- ruff (禁 print / 禁同步阻塞)
- ruff format
- mypy
- tsc --noEmit
- eslint

不通过不能提交 PR。

### 2. 检查分支命名

```bash
python scripts/check_branch.py
```

### 3. 更新 roadmap

如果完成了 `spec/roadmap_开发路线图.md` 中的任务：

- 任务完成并验证通过 → 标记 `✅`
- 追加完成日期和备注：
  ```
  > 完成: YYYY-MM-DD, 备注: <关键决策/遗留问题>
  ```
- 如果实现中做出与 SPEC 不同的决策 → 同步更新对应的 SPEC 文件

### 4. 生成 worklog

```bash
python scripts/gen_worklog.py <你的名字> <简短描述>
```

示例：
```bash
python scripts/gen_worklog.py 黎 fix-websocket-reconnect
```

然后编辑生成的文件，填写：目标、产出、关键决策、未完成、交接信息。

### 5. 更新 STATUS.md

- 修改 `.agenthub/worklogs/STATUS.md` 中你的那一行
- 更新"最后更新"日期为今天
- 更新"正在做"为你下一个任务
- 更新"这周完成了"加上本次完成的功能

### 6. Commit + Push

```bash
git add .
git commit -m "feat: <功能简述>"
git push origin HEAD
```

### 7. 创建 PR（自动）

```bash
gh pr create --title "feat: <功能简述>" --body "<改动说明>" --base main
```

### 8. 日志检查（自动）

push 之前 pre-commit 的 `worklog-check` 钩子会自动检查：
- 今天是否写了 worklog
- STATUS.md 日期是否更新

不通过会阻止 push。

---

## 检查清单

- [ ] `verify.bat` 全部通过
- [ ] 分支命名符合规范
- [ ] roadmap 验收状态已更新
- [ ] worklog 已写（内容完整）
- [ ] STATUS.md 已更新
- [ ] PR 已创建（gh pr create）
