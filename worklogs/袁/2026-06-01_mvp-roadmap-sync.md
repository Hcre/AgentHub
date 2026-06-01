# 工作日志：MVP 收尾冲刺规划同步（roadmap+status+后续升级计划）

- **谁**: 袁（Mavis 代笔）
- **日期**: 2026-06-01
- **分支**: chore/mvp-roadmap-sync
- **关联 Spec**: `docs/plan/后续升级计划/后续计划.txt` v1.0（本次新建）

## 目标
把课题要求 vs 现状的差距分析结果，落到 roadmap 的"MVP 收尾冲刺"清单 + STATUS，并启动 dashboard 验证。

## 产出
- [ ] commit — `docs(plan): sync MVP 收尾冲刺到 roadmap`
- [x] 新建 `docs/plan/后续升级计划/后续计划.txt` v1.0（8 节 MVP/未实现清单）
- [x] 修改 `docs/plan/开发清单_roadmap.md`
  - §八 新增 "MVP 收尾冲刺（M5+：6/2-6/9）" 4 子节：必修/加分/MVP不做/Demo脚本/风险降级
  - §九 新增"变更记录"
  - 不动原 M1-M6（保留时间线记录）
- [x] 修改根 `STATUS.md`
  - 日期 2026-05-31 → 2026-06-01
  - 袁行"正在做"更新 + 这周完成追加
- [ ] 启动 `python scripts/start_server.py` 后台运行 → http://127.0.0.1:8080/dashboard.html 验证
- [ ] worklog: 本文件

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 走 `chore/mvp-roadmap-sync` 分支，不直接 main commit | PR-02 红线 | 需后续推 PR → merge |
| roadmap 不动 M1-M6，追加 §八 M5+ | 保留历史时间线 + 评审看进度时一目了然 | 文档长度 +30% |
| Pin/Diff/文件附件标 P0-1~3 必修 | 课题 4 产物预览是评审核心抓手 | 占用 6/2-6/5 共 ~20h |
| 桌面/移动/部署 标 MVP 不做 | 课题标记 P2 + 时间盒 9 天 | 答辩时显式声明超纲 |
| Demo 脚本写进 §八 8.4 | 3min 视频是交付物，6/9 前必须录 | 评审节奏可控 |
| Worklog 由 Mavis 代笔 | 实际操作者是 AI（git user.name = xiangbianpangde） | 流程合规 + 留痕 |

## 后续计划 v1.0 关键结论

- **MVP 覆盖度 ~70%**（6 大功能维度估算）
- **必修 6 项（P0-1~6）总工时 ~28h**（2 个工作日）
- **加分 4 项（P1-1~4）总工时 ~15h**
- **答辩最强抓手**：
  1. 4 个 CLI 适配器 + CLI×Provider 矩阵（创新 10%）
  2. SPEC/Skill/Rules/ADR 完整沉淀（AI 协作 30%）
  3. 5 层洋葱 + CLI/SDK 双轨架构（代码理解 15%）
- **必修 P0 链**：网页预览 iframe → Diff 视图 → 文件附件 → Pin UI → 复制/重生成 → Demo 数据集

## 给下一位的交接

- **Mavis（后续会话）**：
  - 任务描述里说"实现 P0-1 网页预览 iframe 卡片"，先读 `docs/specs/04-commands_命令接口.md` + `04c-adapter-interface` 再动手（PR-01）
  - 开工前 `git fetch` 同步 main，看本 worklog 是否已 merge → 顺接 chore/mvp-roadmap-sync 分支
  - P0 任务在 issue tracker 不存在，需要建 issue 或在 worklogs/黎/、董/ 下追加子任务

- **董 / 黎**：
  - P0-1~P0-6 可分到不同分支并行（如 `feature/chat/inline-iframe-card`、`feature/chat/diff2html-view`、`feature/chat/file-attach`）
  - P1-3 CLI PATH 扫描前端展示 跟 黎的 provider_scanner 后端强耦合，等黎确认 API 形态

- **袁**（自己）：
  - 答辩前 1 周：跑一次 `scripts/check_worklog.py` + `check_docs.py` 验 pre-push 钩子
  - 答辩前 1 天：录 Demo 备份
  - 答辩后：写收束报告到 `docs/reports/`

- **临时约定**：
  - 本次 git 身份用袁的（xiangbianpangde），Mavis 代笔规范流程；以后 AI Agent 操作都走相应的人的目录
  - 6/1 之前的工作日志都已 merge 进 main，本 worklog 是 6/1 唯一入口

## 未完成 / 阻塞
- [x] 启动 dashboard.html → http://127.0.0.1:8080/dashboard.html 200（PID 55944 端口 8080 监听，**非本会话启动**，是上一会话遗留）
- [x] commit — `e56806e docs(plan): sync MVP 收尾冲刺到 roadmap+status+worklog`
- [x] commit — `a43e7c3 chore(docs): 规范入口/边界/红线文件重命名`（4 个 100% rename，CLAUDE/README → *-规范导航，99-* → 09/10-*）
- [x] push → `origin/chore/mvp-roadmap-sync`
- [x] 开 PR #15 — https://github.com/Hcre/AgentHub/pull/15
- [ ] **PR-06 ≥1 Approve**（待评审组过审）
- [ ] 后续计划 v1.0 评审组过审（待评审）

## 闭环备注（15:58 追加）

第二轮推进把 4 个 conventions 命名按用户指令 a) 一起塞进 `chore/mvp-roadmap-sync`：
- 用 `git add -A docs/conventions/` 让 git 自动按 100% 相似度检测为 rename，保留历史
- 单独 commit `a43e7c3` 而非 amend `e56806e`，保持 commit message 单一职责
- 8 个变更（4 删 + 4 新增）= 4 个 rename，diff 净增 0 行

**关于 4 个规范的旧路径引用**：
- `docs/conventions/CLAUDE-规范导航.md` 等需要自查哪些地方引用了 `99-boundaries_*.md` / `99-process-rules_*.md` / `CLAUDE.md`（旧）
- pre-push 钩子 `check_docs.py` 不一定检查到内部引用，需人工跑 `rg "99-(boundaries|process-rules)" docs/` 查引用
- 如果评审前发现引用断链，可以新 commit 修，不必再开新分支

**下一步动作**（评审组视角）：
1. 评审组过 PR #15（仅 docs 类，风险低，预计 1-2h）
2. 通过后 squash merge → main
3. 6/2 开工 P0-1 网页预览 iframe 卡片（按 PR-02 + 04 API 冻结 + 分支 `feature/chat/inline-iframe-card`）

## 闭环备注（16:12 追加 — bf93c4e 引用修复踩坑）

第三轮推进把 21 处旧路径引用按用户指令 a) 一次到位，但**踩坑了**：

### 第一次尝试（失败 → 立刻回滚）

用 PowerShell 的 `[System.IO.File]::WriteAllText($path, $string, $encoding)` 走 string 中转：
- 破坏 UTF-8 BOM / CRLF
- 10 个文件被乱码（`版本: v3.0` 变成 `鐗堟�?` —— GBK 字节被 UTF-8 解码）
- git diff 看到 22+/22- 但内容全是乱码

**救场**：`git checkout HEAD -- docs/` 立刻回滚 → 4 个 rename + 21 处旧路径全部恢复，工作树干净。

### 第二次尝试（成功）

改用 **字节级 Read/Write**（`ReadAllBytes` + `MemoryStream` 字节级模式匹配 + `WriteAllBytes`）：
- UTF-8 里 ASCII 1 字节 1 字符，和中文 3 字节不会混淆
- 模式 `99-process-rules` / `99-boundaries` 全是 ASCII，字节级安全
- 编码 / BOM / CRLF 全部原样保留

最终 `bf93c4e fix(docs): 同步 4 个规范 rename 的 21 处交叉引用`：
- 10 文件 +22/-22（22 行变 = 11 行原内容 99-/10-/09- 替换）
- 0 残留（`Select-String` 全量扫 docs/ + src/ + scripts/）
- 中文显示正常（`版本: v3.0` / `流程合规校验` / `Agent 操作权限`）

### 教训（已写入 agent memory）

跨项目适用：**中文 / 混合语言 markdown 批量字符串替换必须走字节级**。PowerShell 5.1 的任何 string 中转都会破坏编码。
- 反模式：`Get-Content -Raw` + `-replace` + `Set-Content`
- 正解：`ReadAllBytes` → 内存流字节级匹配 → `WriteAllBytes`
- 替代首选：**Edit 工具按 Read 改写**（更稳），或 **Python 字节脚本**（跨平台无歧义）

### PR #15 最终状态

```
6ccbbbc  docs(worklog): 闭环 PR #15 推送记录 + 引用自查清单  (e56806e+a43e7c3)
bf93c4e  fix(docs): 同步 4 个规范 rename 的 21 处交叉引用    (本次)
a43e7c3  chore(docs): 规范入口/边界/红线文件重命名
e56806e  docs(plan): sync MVP 收尾冲刺到 roadmap+status+worklog
```

**风险评估**：4 个 docs-only commit，零代码改动，零运行时影响。评审组可放心 squash merge。
