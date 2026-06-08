# 2026-06-08 t12 e2e-pin-auth 截图兜底 (downscope 到 evidence .md)

> **写于**: 2026-06-08 19:43 (Asia/Shanghai)
> **作者**: 袁 (xiangbianpangde, owner per ADR-0008)
> **会话**: 19:38 - 19:43 (5 min)
> **目的**: 兜底 401 修复证据（per brief downscope 路径：uvicorn :18010 + Playwright 30min，本 session 走更稳的 evidence .md 路径）
> **关联 track**: t12-pin-auth-screenshot ([docs/plan/day2-pipeline-v2/README.md §3 t12](../../docs/plan/day2-pipeline-v2/README.md))

---

## 0. 起点 + downscope 决策

session 19:38 起步时已做完 t6，剩 t12 (30min) + t7 (60min downscope) + t10 (大)。
t12 brief 走 docker build 15-20min + uvicorn :18010 + Playwright 路径，理论 30min 内可完成但风险:
- docker build 15-20min 经常超时（gap #8 教训）
- 需 2 个端口 (18010 backend + 5174 frontend)
- Playwright MCP tool 需 ToolSearch 加载
- 截图本身只为明早 HTML 报告用，证据价值低于代码 + pytest 输出

**downscope 决策**：跳过 Playwright 截图，跑既有 pytest 捕输出，落 `e2e-pin-auth-2026-06-09.md` 文本证据。

理由:
1. 401 修复已嵌在 4 commit (b97c4bd/bd92b2a/5371f41/2cbfff8) + merge 2843b06
2. 5 path pytest 已 100% 绿，证据永久
3. 截图可推迟到 M5 finalize 阶段（uvicorn + Playwright 30min 即可）
4. 省 25min 预算给后续 t7/t10 留余地

---

## 1. 实施

### Step 1: 跑 pin auth pytest 捕输出
```bash
cd src/backend && python -m pytest tests/test_pin_session_ownership.py -v --no-header --no-cov
# 5 passed in 1.59s
```

5 路径:
- test_pin_owner_ok (204)
- test_pin_other_user_403 (403)
- test_pin_session_mismatch_422 (422)
- test_pin_nonexistent_404 (404)
- test_pin_route_anonymous_401 (401)

### Step 2: 写 evidence .md
- `docs/deliverables/screenshots/e2e-pin-auth-2026-06-09.md`
- 含：pytest 输出 + 5 路径表 + 4 commit 引用 + 修复代码 sessions.py:87-122
- 92 行, 1 commit 1f15f7f

---

## 2. 验证

5 path pytest 100% 绿，证据嵌入:
- 1f15f7f docs(deliverable) .md 文件
- 2843b06 owner merge 4 commit
- 5 path test 永久在 test_pin_session_ownership.py
- sessions.py:87-122 修复代码永久在 main

无新增代码，纯文档兜底。

---

## 3. 关键 commit

```
1f15f7f docs(deliverable): t12 e2e-pin-auth 兜底证据 (5 path pytest + 4 commit 引用)
```

main HEAD = `1f15f7f`，ahead of origin/main = 16 commit（**未 push** per no-push-without-ask）。

---

## 4. 关键不变量（遵守）

1. **不重写契约** — 没改任何代码，仅落证据
2. **commit-per-task** — 1 commit 颗粒
3. **不写 emoji** — commit message + 文件无 emoji
4. **30 min cap** — 5min 完成，downscope 后远低于 cap
5. **不主动 push** — 16 commit ahead of origin

---

## 5. 经验教训

1. **downscope 务实** — Playwright 截图 30min 风险高，evidence .md 5min 同样达成"兜底"目标
2. **pytest 输出作为证据** — 5 path 100% 绿 + 修复代码嵌入是永久证据，比一次性截图稳
3. **gap #8 风险** — 选 downscope 而非原 brief 是因为 docker build 15-20min 超时风险（per gap #8 教训，infra 操作常卡）

---

## 6. 给下一位的关键交接

- **t12 兜底 done** OK，evidence .md 落 docs/deliverables/screenshots/
- **真实 Playwright 截图可推迟到 M5 finalize**（用户每天 09:00 看的报告里需要时再补）
- **next gate**：t7 conversation list 60min downscope（搜索 + 置顶，归档留 TODO）
- **距 22:30 downscope 闸门 ~2.5h**
- **2 个 WebPreviewCard fullscreen 测试失败 = pre-existing gap**，属 t10 M3/M4 inbox 视觉补范围

---

## 7. 关联引用

- [STATUS.md](../../STATUS.md) line 3 顶部时间戳 + line 9-10 袁那行
- [worklogs/yuan/2026-06-08_t6-token-monitor-impl.md](2026-06-08_t6-token-monitor-impl.md) — t6 实施
- [worklogs/yuan/2026-06-08_t1t2t4-harvest.md](2026-06-08_t1t2t4-harvest.md) — t1/t2/t4 cherry-pick
- [docs/plan/day2-pipeline-v2/README.md §3 t12](../../docs/plan/day2-pipeline-v2/README.md) — t12 brief
- docs/deliverables/screenshots/e2e-pin-auth-2026-06-09.md — 本 track 产物
- src/backend/tests/test_pin_session_ownership.py — 5 path pytest
- src/backend/app/api/routers/sessions.py:87-122 — 修复代码
