# M-EV01 框架决策记录 FDR-M-EV01-MCP-V1.0-20260603

> 4 项关键决策
> [DD-M推断 / DD-001 引用]

---

## FDR-M-EV01-001

```
[决策编号] FDR-M-EV01-001
[决策标题] 关键 topic 强制 Stream 模式
[决策状态] 已接受
[决策内容] 5 主题中 5 个细分事件（approval.*/process.*/mcp.*）强制使用 Redis Stream + consumer group
[决策理由] [AR洞察-1] 关键事件需持久化与至少一次投递；Pub/Sub 不保证投递
[拒绝的替代方案] 全部走 Pub/Sub（拒绝理由：易丢消息，无法 DLQ）
[影响范围] bus.py::publish / stream_consumer.py / __init__.STREAM_TOPICS
[相关FDR] -
[来源标注] [DD-001:AR洞察-1 + DDR-002 + MD-MCP-V1.0-M-EV01]
```

## FDR-M-EV01-002

```
[决策编号] FDR-M-EV01-002
[决策标题] schemas 按 topic 拆 5 文件（vs 单文件）
[决策状态] 已接受
[决策内容] schemas/ 目录下按 5 topic 各拆 1 文件（approval/template/process/mcp/binding）
[决策理由] 利于跨团队并行维护 + 减小 merge 冲突 + 单一职责
[拒绝的替代方案] 单文件 schemas.py（拒绝理由：单文件 200+ 行不利于维护与权限细分）
[影响范围] schemas/{approval,template,process,mcp,binding}.py
[来源标注] [DD-M推断:依据 FS-022 + 单一职责原则]
```

## FDR-M-EV01-003

```
[决策编号] FDR-M-EV01-003
[决策标题] handler 异常统一转 DLQ
[决策状态] 已接受
[决策内容] Stream 模式下 handler 异常 / 超时统一转 <topic>.dlq stream
[决策理由] [MD-MCP-V1.0-M-EV01] 异常处理；防止阻塞 consumer group
[拒绝的替代方案] 阻塞重试（拒绝理由：可能耗尽 consumer group 处理能力）
[影响范围] stream_consumer.py::_handle_message / _move_to_dlq
[来源标注] [DD-001:MD-MCP-V1.0-M-EV01 + AR洞察-1]
```

## FDR-M-EV01-004

```
[决策编号] FDR-M-EV01-004
[决策标题] Schema 版本独立（v1 起步，向后兼容）
[决策状态] 已接受
[决策内容] Schema 使用 v1 版本号 + $id 嵌入；升级保留旧版至少 1 发布周期
[决策理由] 避免 schema 升级导致多版本消费者解析失败
[拒绝的替代方案] 不带版本（拒绝理由：未来升级风险不可控）
[影响范围] schemas/* $id 字段；registry.py SCHEMA_VERSION 常量
[来源标注] [DD-M推断:依据 CS-§7 + 渐进式升级原则]
```
