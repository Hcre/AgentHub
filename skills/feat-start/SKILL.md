---
name: feat-start
description: Start a new feature — read spec, create branch, update STATUS, generate worklog stub. Use when beginning work on a new feature.
---

# feat-start: 开始新功能

> **一键执行**: `scripts\feat-start.bat`
> **Linux/WSL**: `bash scripts/feat-start.sh`

## 适用时机

- 领取 roadmap 中的一个任务
- 开始一个新的 feature/fix/refactor
- 切换工作上下文

## 执行步骤

### 1. 同步代码 + 读状态

```bash
git pull origin main
```

读 `docs/plan/开发清单_roadmap.md` 确认当前进度。
读 `conventions/CLAUDE-规范导航.md` 红线总表（AR/CR/PR/AP/T/D）确认红线。

### 2. 读相关 SPEC

根据任务类型，读对应的 SPEC 文件：

| 任务 | 必读文档 |
|------|---------|
| 后端开发 | `docs/specs/01b-architecture-design_分层与数据流.md` + `docs/specs/03-data-model_数据模型.md` |
| API 开发 | `docs/specs/04-commands_命令接口.md` + `conventions/99-boundaries_边界矩阵.md` |
| 前端开发 | `docs/plan/背景_PRD_AgentHub_统一方案.md` + `docs/specs/04-commands_命令接口.md` |
| Agent 集成 | `docs/specs/04c-adapter-interface_适配器接口规范.md` + `docs/specs/01-architecture_架构定义.md` |

### 3. 创建分支

```bash
git checkout -b feature/<domain>/<desc>
```

分支命名规范（PR-02）：`feature/{domain}/{desc}`，如 `feature/chat/websocket-endpoint`

### 4. 更新 STATUS.md

- 修改"正在做"为当前任务
- 更新"最后更新"日期

### 5. 生成 worklog 模板

```bash
python scripts/gen_worklog.py <你的名字> <简短描述>
```

示例：
```bash
python scripts/gen_worklog.py 黎 add-websocket-heartbeat
```

### 6. 开发

遵循 `CLAUDE.md` 中的行为准则和 `conventions/CLAUDE-规范导航.md` 红线总表（AR/CR/PR/AP/T/D 全集）。

---

## 检查清单

- [ ] git pull 已完成
- [ ] 相关 SPEC 已读
- [ ] 分支已创建且命名正确
- [ ] STATUS.md 已更新
- [ ] worklog 模板已生成
