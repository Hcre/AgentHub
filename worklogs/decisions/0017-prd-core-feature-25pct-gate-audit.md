# ADR-0017: M5 范围 PRD 核心功能 25% 闸门对账 + M5/M6 缺口计划

- **状态**: Accepted
- **日期**: 2026-06-07 22:00 (Asia/Shanghai, 与 [ADR-0014](0014-mavis-team-plan-ba86c4d0-strong-close.md) 同步)
- **决策者**: 袁 (xiangbianpangde, owner, per ADR-0008)
- **关联 worklog**: `worklogs/袁/2026-06-08_t5-f9-s2-pin-copy-owner-takeover.md`
- **关联 SPEC**: `docs/plan/背景.md` 25% 闸门（line 15-56 核心 6 大功能）

## 背景

PRD 考察要点"功能完整度 25%" = 6 大核心功能（IM 聊天/Orchestrator/多 Agent 接入/产物预览/部署/多端）。需要客观对账当前实际状态与 PRD 承诺。

## 对账方法

1. **代码现状**：基于 `plan_ba86c4d0` 7 impl commit 落 main (`eea1d0e`) + 凌晨冲刺 4 commit
2. **E2E 实测**：Playwright MCP 11 章节 + 6-7/6-8 Phase 1/2（per ADR-0016）
3. **静态阅读**：核心模块源码（sessions.py / MessageBubble / AgentsListPage）

## 结果

| 维度 | 完整 | 部分 | 未做 | 计划 |
|------|------|------|------|------|
| 1. IM 聊天 | 4 | 1 | 0 | 0 |
| 2. Orchestrator | 2 | 0 | 1 | 0 |
| 3. 多 Agent 接入 | 2 | 1 | 0 | 0 |
| 4. 产物预览 | 5 | 0 | 2 | 0 |
| 5. 【P2】部署 | 1 | 1 | 0 | 0 |
| 6. 【P2】多端 | 1 | 0 | 0 | 1 |
| **合计** | **15** | **5** | **5** | **1** |

覆盖率 = (15+5×0.5)/(15+5+5+1) = **17.5/26 = 67%**（含部分实现折半）

## 决策

- 接受当前 67% 覆盖率作为 M5 终点（含"部分"折算）
- 6 项核心必修 P0（P0-1~6）已 5/6 done，唯一缺口 P0-4 Pin API 401 + alembic dual head 留 M5/M6 手动补 ~1-2h
- 移动 H5 之前 STATUS 误判为 ✅，本次对账纠正为 ❌ 未实现（与 Playwright 768×1024 实测一致）
- 桌面端 Tauri 2 仍按 ADR-0007 走，不在 M5 范围

## M5/M6 工作量

| 项目 | 估时 | 优先级 |
|------|------|--------|
| P0-4 Pin session 校验 + alembic 0014 merge | ~1h | 🔴 高 |
| P0-4 Pin API 401 修复 | ~1-2h | 🔴 高 |
| P1-2 Token 监控 E2E 收尾（main.py router 注册） | ~30min | 🟡 中 |
| P1-3 CLI PATH 扫描 scheduler 集成 | ~1h | 🟡 中 |
| F10 移动 H5 响应式（4 栏 shell + useMediaQuery） | ~3-5d | 🟡 中 |

## 反模式

- 不要再以"commit message 自报 ✅"作为完成度证据（6/7 Pin API 401 + 移动 H5 都是 commit ✅ 但代码未交付的反例）
- 6/8 后所有 P0 验收必须经 Playwright E2E 复跑 + 控制台 0 错 0 警 + 至少 1 张截图（per ADR-0016）
