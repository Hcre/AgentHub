# Pre-push Hook 增强建议

> 基于 2026-05-31 OpenCode 集成实战教训 + 文档规范 D-01~D-12 缺口

## 当前 Hook 覆盖

| 钩子 | 阶段 | 覆盖 |
|------|------|------|
| ruff | pre-commit | Python lint |
| eslint | pre-commit | 前端 lint |
| tsc-typecheck | pre-commit | TS 类型 |
| branch-name | pre-push | 分支命名 |
| worklog-check | pre-push | worklog 存在性 |
| doc-check | pre-push | D-05~D-12 文档结构 |

## 建议新增（优先级排序）

### P0 — 今天出过事的

**1. `check-no-skip-hooks` — 禁止 --no-verify**
- 今天用 `--no-verify` 跳过了 worklog 检查直接 push
- 实现: `git rev-list` 检查推送的 commits 是否标记了 `--no-verify`
- 阶段: pre-push

**2. `check-api-key-leak` — 密钥泄露扫描**
- ProviderScanner、opencode_runtime 等文件里硬编码过 `sk-xxx`
- 实现: regex `sk-[a-zA-Z0-9]{20,}` / `Bearer [a-zA-Z0-9]{20,}`
- 阶段: pre-commit (仅 diff) + pre-push (全量)
- 对应规范: 新增安全红线

**3. `check-migration-complete` — 数据库迁移未提交检查**
- 今天 Postgres/SQLite 双库导致数据不一致
- 实现: 检查 `alembic/versions/` 是否有未 git add 的新文件
- 阶段: pre-push

### P1 — 文档规范覆盖缺口

**4. `check-dead-doc-links` — 文档死链检查**
- D-11 要求 CLAUDE.md 引用可解析，但只检查了 CLAUDE.md
- 扩展: 检查所有 `docs/**/*.md` 中的 `]` 内部链接
- 阶段: pre-push

**5. `check-docstring-public-api` — 公共 API docstring 检查 (D-03)**
- D-03 要求公共 API 有 docstring，目前完全靠 CR
- 实现: 检查 `__all__` 导出的函数/类是否有 docstring
- 阶段: pre-commit

**6. `check-template-compliance` — 模板使用检查**
- 规范要求从模板起步，目前完全靠人工
- 实现: 检查 worklog 是否包含必填段（做了什么/关键决策/待办）
- 阶段: pre-push

### P2 — 质量保障

**7. `check-circular-import` — 循环导入检查**
- 五层洋葱架构要求依赖单向，目前无自动检查
- 实现: `import-linter` 或手写 AST 检查
- 阶段: pre-commit

**8. `check-commit-format` — Commit message 格式**
- 混用了中英文、有/无 scope、有/无前缀
- 实现: regex 匹配 `^(feat|fix|docs|refactor|test|chore)(\(.+\))?: .+`
- 阶段: pre-push (用 commit-msg hook)

**9. `check-test-before-merge` — 合并前测试**
- 今天合并前没有跑测试
- 实现: `pytest --cobertura` + 覆盖率不下降
- 阶段: pre-push (慢，可并行)

### P3 — 运维

**10. `check-stale-branch` — 僵尸分支提醒**
- 实现: 检查当前分支是否已合并到 main，提示删除
- 阶段: post-commit

## 实施路线

```
今天: P0-1 (防 --no-verify) + P0-2 (防密钥泄露)
本周: P0-3 + P1-4/5/6
下周: P2-7/8/9
```
