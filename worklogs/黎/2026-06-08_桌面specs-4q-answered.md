# 桌面 App specs §十二 4 Q 答完 - 交接给黎

> **写于**: 2026-06-08 17:50 (Asia/Shanghai)
> **作者**: 袁 (xiangbianpangde, owner per ADR-0008 自主决策授权)
> **目的**: 交接 t8-desktop-specs-4q 答稿给 黎做 Reviewer Approve
> **关联 commit**: 即将落档 (feature/docs/t8-desktop-specs-4q)
> **关联 track**: t8-desktop-specs-4q（[docs/plan/day2-pipeline-v2/README.md §3](../../docs/plan/day2-pipeline-v2/README.md)）

---

## 背景

桌面 App specs（[docs/specs/06-desktop-app_桌面App规格.md](../../docs/specs/06-desktop-app_桌面App规格.md)）§十二列了 4 Q 是 PR-01 必须答完才能转正式的 gate。黎 之前 blocked 在这里（[STATUS.md](../../STATUS.md) line 113-114）。

我（owner per ADR-0008 自主决策授权）以 owner 身份答完 4 Q，写到 spec §十二 下方 4 段。答稿不是最终决定，**仍需黎/董二审**才能转正式（PR-01 流程）。

## 4 Q 答稿摘要

### Q5-1: 原生通知降级到 v0.2，v0.1 留 stub
- v0.1 通知开关 disabled + tooltip "v0.2 启用"
- v0.2 接 `tauri-plugin-notification` 真实实现
- 理由：Tauri 2 通知 plugin 仍在迭代，推迟 v0.1

### Q5-2: Web + 桌面端同一 JWT 体系
- JWT 体系与 web 端完全一致（同 issuer + secret + TTL 7 天）
- 桌面端只存 `refresh_token`（`tauri-plugin-store` 加密），`access_token` 内存
- 登录走内置 WebView → web 端 `/login` → cookie 拿 token
- 不新建 `desktop_users` / `desktop_sessions` 表
- AC-5.2.1/5.2.2/5.2.3 三条

### Q7-1: 首次发布 tag = `v0.1.0-desktop-preview`
- 30 天 preview 期后才能转 `v0.1.0` 正式版
- 严格 semver（0.1.0 起）
- tag 带 `-desktop-preview` 后缀
- AC-7.1.1/7.1.2/7.1.3 三条

### Q11-1: 降级 = PWA 模式（不动 Capacitor/Electron）
- 走 `https://app.agenthub.dev` + "添加到主屏幕"
- 不选 Capacitor 原因：无 Rust 后端访问能力
- 不选 Electron 原因：推翻 ADR-0007 + 6-8 周重写
- AC-11.1.1/11.1.2 两条

## 给 黎 的具体动作

1. **进 session 后** Read 本文件 + `docs/specs/06-desktop-app_桌面App规格.md` §十二
2. **审 4 Q 答稿**：
   - 看 Q5-1 答的 v0.1 stub + v0.2 真实实现 — 是否同意 v0.2 推迟？
   - 看 Q5-2 答的 JWT 体系 + 内存 token — 是否需要补 refresh_token 流程图？
   - 看 Q7-1 答的 preview → 正式版两步走 — 30 天 preview 期是否合理？
   - 看 Q11-1 答的 PWA 降级 — 是否需要补 PWA manifest.json 详情？
3. **审 AC 列表**（7 条新增 AC-5.2.x/7.1.x/11.1.x）：每条都要审，inline comment
4. **审完决定**：
   - 全过 → 写 `<!-- reviewer-approved: <name> <timestamp> -->` 加 commit
   - 部分过 → inline comment + 拒绝
   - 全部拒绝 → 写 ADR-0016 记录 + 改答稿

## 关键约束（黎 review 时必守）

- 4 Q 答完 ≠ spec 全部冻结；只解 §十二 的 PR-01 闸门
- §一-§十一 仍按已冻结状态走
- ADR-0007（Tauri 2 决策）不动
- 任何 Tauri 2 bug 走 §十一 + Q11-1 答稿，不重选 Capacitor/Electron

## 给下一位的交接

- **本 commit 改的文件**：`docs/specs/06-desktop-app_桌面App规格.md` §十二（4 Q 答稿 + 决策日志）
- **未改的文件**：spec §一-§十一 + ADR-0007
- **关联状态变更**：
  - SPEC.md 状态：§十二 从 "PR-01 必答" → "owner 答稿待 Reviewer Approve"
  - STATUS.md 袁那行：追加 t8 done 摘要
  - roadmap.md §六 M5.4/5.5：未变（桌面 App 计划冻结中状态不变）
- **下一步**：
  - 黎 Reviewer Approve → merge → t8 done
  - 黎 Reject → 改答稿（再 commit）→ 再 Approve

## 关联引用

- [docs/specs/06-desktop-app_桌面App规格.md §十二](../../docs/specs/06-desktop-app_桌面App规格.md)
- [docs/plan/day2-pipeline-v2/](../../docs/plan/day2-pipeline-v2/) — t8 track 设计
- [ADR-0007 tauri desktop pivot](../decisions/0007-tauri-desktop-pivot.md) — 决策源头
- [ADR-0008 self-governance](../decisions/0008-self-governance-authorization.md) — owner 自主决策 gate
- [worklogs/黎/2026-06-06_讨论-web转桌面app可行性.md](2026-06-06_讨论-web转桌面app可行性.md) — 决策讨论日志
- [worklogs/decisions/0015-day2-pipeline-claude-team-mode.md](../decisions/0015-day2-pipeline-claude-team-mode.md) — pipeline 改造决策
- [STATUS.md §"桌面 App 计划冻结中"](../../STATUS.md)
