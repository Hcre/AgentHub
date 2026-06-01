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
- [ ] 启动 dashboard.html（待本会话最后一步执行）
- [ ] commit + PR（待人 review）
- [ ] 后续计划 v1.0 评审组过审（待评审）
