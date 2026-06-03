# 文件框架结构 FF-M-A04-MCP-V1.0-20260603

> 模块：M-A04 Cron Scheduler
> 路径：产出物/07-文件框架/M-A04/M-A04-cron/
> 来源：[DD-001:FS-004 / MD-MCP-V1.0-20260602.md#M-A04]

---

## 文件框架

```
M-A04-cron/
├── __init__.py          ← 模块初始化；导出 CronApp/LeaderElector/JobDispatcher/CronAuditor
├── app.py               ← CronApp（DaemonSet 入口）；start/stop/healthz/readyz
├── scheduler.py         ← CronScheduler（APScheduler 封装）；load_jobs/start/shutdown/_on_trigger
├── leader_elector.py    ← LeaderElector（Redis SETNX）；acquire/renew/release/start_heartbeat
├── dispatcher.py        ← JobDispatcher（arq enqueue）；dispatch/dispatch_with_retry
├── auditor.py           ← CronAuditor（trigger.cron.fired 事件）；on_trigger
└── tests/
    ├── __init__.py
    ├── test_app.py              ← CronApp 集成（6 场景：单/多实例/leader 切换/stop/探针）
    ├── test_scheduler.py        ← CronScheduler 单元（5 场景：加载/触发/相位/shutdown）
    ├── test_leader_elector.py   ← LeaderElector 单元（7 场景：抢/竞争/续约/让位/相位）
    ├── test_dispatcher.py       ← JobDispatcher 单元（5 场景：派发/重试/序列化）
    └── test_auditor.py          ← CronAuditor 单元（3 场景：正常/失败/best-effort）
```

## 文件间依赖关系

```
app.py → scheduler.py → dispatcher.py → arq.Redis (M-D03)
              ↓
              auditor.py → eventbus (M-EV01)
              ↓
       leader_elector.py → redis (M-D03)
```

严格单向依赖，无循环导入。app.py 不直接调用 dispatcher/auditor；scheduler.py 编排。

## 文件职责单一性

| 文件 | 单一职责 | 函数/类数 | 是否合规（R24） |
|------|---------|----------|---------------|
| app.py | 生命周期编排 | 1类4方法 | 是 |
| scheduler.py | 调度 | 1类4方法 | 是 |
| leader_elector.py | 选举 | 1类4方法 | 是 |
| dispatcher.py | 派发 | 1类2方法 | 是 |
| auditor.py | 审计 | 1类1方法 | 是 |

## 来源标注

- 全部 10 个 .py 文件 100% 含 [来源标注] 字段
- 标注来源：[DD-001:FS-004 / MD-MCP-V1.0-20260602.md#M-A04] 或 [DD-M推断:依据]
- 推断标注率 = 100%（仅 Redis 客户端类型、trace_id 规则等非 DD-001 原文处使用 [DD-M推断]）
