# 框架决策记录 FDR-M-A04-MCP-V1.0-20260603

> 模块：M-A04

---

## FDR-001 文件目录带 M-A04 编号前缀

[决策编号] FDR-001
[决策状态] 已接受
[决策内容] 产出物目录使用 `M-A04/M-A04-cron/` 双层编号，避免多 DD-M 实例冲突
[决策理由] soul 6.1 要求"带注释的代码文件路径必须包含模块编号"；多实例隔离协议 7.3 要求命名带模块编号前缀
[拒绝的替代方案] 方案 B：使用 `cron/` 单层目录——多 DD-M 实例并行时与 M-A02/M-A03 等命名冲突（"cron" 在其他项目可能复用）
[影响范围] 全部 M-A04 产出物路径
[相关FDR] 无
[来源标注] [DD-M推断:基于 soul 6.1 + 7.3 多实例隔离协议]

## FDR-002 LeaderElector TTL 60s/心跳 30s

[决策编号] FDR-002
[决策状态] 已接受
[决策内容] TTL 60s 远大于心跳 30s，避免网络抖动导致误让位
[决策理由] MD-A04 注释明确"renew_fail(60s) → Standby"；心跳 30s 提供 2 次容错窗口
[拒绝的替代方案] 方案 B：TTL=心跳=30s——单次网络抖动即让位，过于敏感
[影响范围] leader_elector.py DEFAULT_TTL_SEC / HEARTBEAT_INTERVAL_SEC
[相关FDR] 无
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 函数签名 renew_leader 心跳 30s]

## FDR-003 错开相位 :00/:15/:45 三实例

[决策编号] FDR-003
[决策状态] 已接受
[决策内容] 多个 CronApp 实例 phase_offset_sec 分别配置 0/15/45，cron trigger 错开
[决策理由] TD:RSK-05 错开 15s 相位；避免每秒雪崩
[拒绝的替代方案] 方案 B：所有实例同相位——每秒 trigger 集中在 :00，雪崩
[影响范围] scheduler.py phase_offset_sec 参数 / K8s DaemonSet env
[相关FDR] 无
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 来源标注 TD:RSK-05]

## FDR-004 派发指数重试 1s/2s/4s

[决策编号] FDR-004
[决策状态] 已接受
[决策内容] arq 派发失败指数重试，max 3
[决策理由] EX-007 明确"DispatchError → arq 重试（指数 1s/2s/4s, max 3）"
[拒绝的替代方案] 方案 B：固定 5s 重试 3 次——慢且不区分瞬时/持续故障
[影响范围] dispatcher.py MAX_RETRIES / RETRY_BASE_SEC
[相关FDR] 无
[来源标注] [DD-001:EX-MCP-V1.0-20260602.md#EX-007]

## FDR-005 框架方案对比结果

[决策编号] FDR-005
[决策状态] 已接受
[决策内容] 主方案 A（按 MD-A04 模板扁平 5 文件）胜出，备选 B（按子模块拆包 scheduler/leader/dispatcher/audit/）未采纳
[决策理由] 评分：A=8.85 vs B=7.05（按 soul 4.11 6 维度加权）。B 过度拆分，单子模块文件仅 1-2 个类，违反 R14 禁止过度拆分
[拒绝的替代方案] 备选 B：scheduler/__init__.py + scheduler/jobs.py + ... 4 子包——文件数膨胀但单文件函数过少
[影响范围] 文件结构 FF-001
[相关FDR] 无
[来源标注] [DD-M推断:基于 soul 4.11 多方案对比 + R14]

## DD-M 洞察注入

- **洞察 1（循环导入风险）**：app.py 不直接 import dispatcher/auditor；通过 scheduler.py 编排依赖，避免 M-A04 内部循环导入
- **洞察 2（健康探针语义）**：healthz 始终 ok，readyz 仅 Leader=True。Standby 实例 K8s 不路由流量，避免重复触发，但 DaemonSet 必须存活以备 leader 切换——已写入 app.py:healthz/readyz 注释
- **洞察 3（MissedRun 跳过）**：崩溃恢复后不补跑错过的 cron trigger，与 [AC:AG-004] 行为一致；scheduler._on_trigger 注释已标注
