# t6-m5-5-3-token-ui (Token 监控 UI) — TODO 文档

> **写于**: 2026-06-08 18:30 (Asia/Shanghai)
> **作者**: 袁 (xiangbianpangde, owner per ADR-0008)
> **状态**: ⬜ TODO — t6 未完成，本文档记录**已落地的最小骨架** + **给下一位的完整实施计划**
> **关联 track**: t6-m5-5-3-token-ui（[docs/plan/day2-pipeline-v2/README.md §3](../../docs/plan/day2-pipeline-v2/README.md)）

---

## 本 session 已落地（最小骨架）

### 1. 端点注册（t9 顺带完成）
- `src/backend/app/main.py`: `app.include_router(usage.router)` 已注册
- 端点: `GET /api/usage` / `/agents/{id}` / `/sessions/{id}` (3 端点, 1h/24h/7d window)
- smoke test: `src/backend/tests/test_usage_router.py` 3 路径全绿

### 2. Service 层 TODO 注释
- `src/backend/app/application/services/usage_service.py`: 已加 `# TODO(t6-m5-5-3-token-ui)` 注释
- 标出 4 步待办: (1) repo interface 加 2 abstract method; (2) Postgres impl; (3) router 加 `/global` 端点; (4) 前端 panel

---

## 完整实施计划（给下一位接手）

### Step 1: Backend - 加 `aggregate_global` 全平台聚合

**文件**: `src/backend/app/domain/repositories/usage_repository.py`（抽象接口）

```python
@abstractmethod
async def sum_global(self, window: UsageWindow) -> dict[str, int]: ...

@abstractmethod
async def group_by_agent_global(
    self, window: UsageWindow, top_n: int = 10
) -> list[dict]: ...
```

**文件**: `src/backend/app/infrastructure/repositories/usage_repository.py`（Postgres impl）

```python
async def sum_global(self, window: UsageWindow) -> dict[str, int]:
    return await self._bucket_sum(
        where_clauses=[UsageRecordModel.created_at >= window.since]
    )

async def group_by_agent_global(
    self, window: UsageWindow, top_n: int = 10
) -> list[dict]:
    stmt = (
        select(
            UsageRecordModel.agent_id,
            func.coalesce(func.sum(UsageRecordModel.tokens), 0).label("total"),
        )
        .where(UsageRecordModel.created_at >= window.since)
        .group_by(UsageRecordModel.agent_id)
        .order_by(func.sum(UsageRecordModel.tokens).desc())
        .limit(top_n)
    )
    rows = (await self._s.execute(stmt)).all()
    return [
        {"agent_id": str(aid), "total_tokens": int(total)}
        for aid, total in rows if aid is not None
    ]
```

**文件**: `src/backend/app/application/services/usage_service.py` — 把 TODO 注释替换为：
```python
async def aggregate_global(self, window_name: str = "24h") -> dict:
    """全平台 Token 聚合（t6 Token 监控 UI 用，不限 agent/session）。"""
    window = UsageWindow.from_name(window_name)
    total = await self._repo.sum_global(window)
    by_agent = await self._repo.group_by_agent_global(window, top_n=10)
    return {
        "window": window_name,
        "since": window.since.isoformat(),
        "prompt_tokens": total["prompt"],
        "completion_tokens": total["completion"],
        "total_tokens": total["total"],
        "by_agent": by_agent,
    }
```

### Step 2: Backend - 加 `/api/usage/global` 端点

**文件**: `src/backend/app/api/routers/usage.py`

```python
@router.get("/global")
async def get_global_usage(
    window: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
    svc: ServiceDep = ...,  # type: ignore[assignment]
) -> dict:
    return await svc.aggregate_global(window_name=window)
```

### Step 3: Backend - pytest 1 路径

**文件**: `src/backend/tests/test_usage_global.py` (新)

3 测:
- `test_usage_global_1h`: 5 records 全在 1h 内 → 5 total
- `test_usage_global_top_n`: 12 agents → 返回 10 个 (top 10)
- `test_usage_global_window_validation`: window=invalid → 422

### Step 4: Frontend - `<TokenMonitorPanel />` 组件

**新文件**: `src/frontend/src/components/settings/TokenMonitorPanel.tsx`

最小骨架（MVP，无 sparkline / 模型分桶 / 移动端）:
```typescript
import { useEffect, useState } from 'react'
import { Dialog, DialogContent, Button, Icon } from '../ui'

interface UsageResp {
  window: string
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  since: string
  by_agent: { agent_id: string; total_tokens: number }[]
}

const WINDOWS = ['1h', '24h', '7d'] as const

export function TokenMonitorPanel({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [data, setData] = useState<Record<string, UsageResp | null>>({})
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setErr(null)
    Promise.all(
      WINDOWS.map(async (w) => {
        const r = await fetch(`/api/usage/global?window=${w}`)
        if (!r.ok) throw new Error(`HTTP ${r.status} for window=${w}`)
        return [w, (await r.json()) as UsageResp] as const
      })
    ).then((entries) => {
      setData(Object.fromEntries(entries))
      setLoading(false)
    }).catch((e) => {
      setErr(String(e))
      setLoading(false)
    })
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[680px]">
        <header className="border-b p-4">
          <h2 className="text-base font-semibold">Token 消耗监控</h2>
          <p className="text-xs text-muted-foreground">实时显示全平台 1h / 24h / 7d 窗口消耗</p>
        </header>
        <div className="grid grid-cols-3 gap-3 p-4">
          {WINDOWS.map((w) => (
            <div key={w} className="rounded-lg border p-3" data-testid={`usage-card-${w}`}>
              <div className="text-xs text-muted-foreground">{w} 消耗</div>
              <div className="mt-1 text-2xl font-mono font-semibold">
                {data[w]?.total_tokens ?? '—'}
              </div>
              <div className="mt-1 text-[10px] text-muted-foreground">
                prompt {data[w]?.prompt_tokens ?? 0} · completion {data[w]?.completion_tokens ?? 0}
              </div>
            </div>
          ))}
        </div>
        {err && <div className="p-3 text-xs text-destructive">{err}</div>}
        {loading && <div className="p-3 text-xs text-muted-foreground">加载中...</div>}
        <footer className="border-t p-3 text-right">
          <Button onClick={() => onOpenChange(false)}>关闭</Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
```

### Step 5: Frontend - 加 NavRail "用量" 入口

**文件**: `src/frontend/src/components/layout/NavRail.tsx`
- `RAIL_ITEMS` 加 1 项: `{ key: 'usage', icon: 'chart', label: '用量' }` (无 section, 弹 modal)
- 引入 `useState` 控制 TokenMonitorPanel open
- 弹 `<TokenMonitorPanel open={usageOpen} onOpenChange={setUsageOpen} />`

### Step 6: Frontend - vitest 单测

**新文件**: `src/frontend/src/components/settings/TokenMonitorPanel.test.tsx`

3 测:
- `renders 3 cards with window labels`
- `fetches /api/usage/global?window=1h|24h|7d on open`
- `displays total_tokens for each card`

### Step 7: 04-commands §六 BDD scenario 追加

**文件**: `docs/specs/04-commands_命令接口.md` §六

```markdown
### t6 B-6-P2-T6: 全平台 Token 监控 1h/24h/7d
**Given**: 平台有 N 个 agent + M 个 session, 各自有 usage_records
**When**: GET /api/usage/global?window={1h|24h|7d}
**Then**: 200 + {window, since, total_tokens, prompt_tokens, completion_tokens, by_agent[top 10]}
**证据**: tests/test_usage_global.py 3 路径 + TokenMonitorPanel.test.tsx 3 路径 + Playwright /api/usage/global E2E
```

### Step 8: 收尾
- 1 commit `feat(backend): /api/usage/global 端点 + 全平台聚合`
- 1 commit `feat(frontend): TokenMonitorPanel + NavRail "用量" 入口`
- `docs/reports/test-report-2026-06-09.html` 落盘
- 1 张 Playwright 截图 `e2e-token-monitor-1280-2026-06-09.png`
- 2 张 mobile 截图 (375/768) 视情况

---

## 验收标准（明早 09:00）

- [ ] `GET /api/usage/global?window=1h` 返回 200 + 正确 JSON
- [ ] 3 卡片（1h/24h/7d）真渲染（Playwright 截图）
- [ ] pytest 171/171 绿（168 + t6 3 测）
- [ ] vitest 102/102 绿（98 + t6 3 测，t9 已加 2 测）
- [ ] NavRail 5 项 (chat/agent/group/skill/usage)
- [ ] 移动端 375 / 768 截图（可选）

---

## 给下一位的关键约束

- **BDD+TDD 双循环**：先写 BDD（04-commands §六）→ 再写 test → 再写 impl
- **不重写契约**：aggregate_global 字段名/类型与 aggregate_by_agent 对齐
- **worktree 隔离**：新开 `feature/backend/t6-token-monitor-global` 分支
- **commit 颗粒**：每步独立 commit (repo / service / router / panel / test)
- **不写 emoji**（CLAUDE.md 红线）
- **Python 禁同步阻塞**（CR-12，repo 必须 async）
- **pre-commit hook 必过**（PR-02/03/07）

## 关联引用

- [docs/plan/day2-pipeline-v2/README.md §3 t6](../../docs/plan/day2-pipeline-v2/README.md) — track 设计
- [docs/specs/04-commands §六](../../docs/specs/04-commands_命令接口.md) — BDD scenario 段
- [src/backend/app/api/routers/usage.py](../../src/backend/app/api/routers/usage.py) — 现有 3 端点
- [src/backend/app/application/services/usage_service.py](../../src/backend/app/application/services/usage_service.py) — Service 层（已加 TODO 注释）
- [src/frontend/src/components/settings/](../../src/frontend/src/components/settings/) — 组件目录
- [src/frontend/src/components/layout/NavRail.tsx](../../src/frontend/src/components/layout/NavRail.tsx) — 入口
- [worklogs/decisions/0015-day2-pipeline-claude-team-mode.md](../../worklogs/decisions/0015-day2-pipeline-claude-team-mode.md) — pipeline 设计
- [worklogs/yuan/2026-06-08_t9-usage-router.md](2026-06-08_t9-usage-router.md) — t9 端点注册（已完成）
- [STATUS.md line 9-10](../../STATUS.md) — 袁那行 t6 next gate
