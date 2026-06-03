# 框架决策记录 FDR-M-C05-MCP-V1.0-20260602

## FDR-M-C05-001 ACLRule 模型归位

```
[决策编号] FDR-M-C05-001
[决策标题] ACLRule 模型内联于 controller.py 而非独立文件
[决策状态] 已接受
[决策内容] ACLRule 数据模型放入 controller.py，不新增 models.py
[决策理由] FS-014 权威结构仅含 controller.py + backends/；独立文件会增加模块边界复杂度
[拒绝的替代方案] 新增 models.py（被拒：违反 FS 权威性）
[影响范围] M-C05 全部
[相关FDR] -
[来源标注] [DD-M推断:FS-014 为文件结构权威源]
```

## FDR-M-C05-002 backend 切换策略

```
[决策编号] FDR-M-C05-002
[决策标题] backend 选型采用探测式 Strategy
[决策状态] 已接受
[决策内容] _select_backend 运行时探测 OS/容器环境选择 iptables / docker_network / ipset
[决策理由] MD-MCP-V1.0 明确采用 Strategy 模式；动态探测避免静态配置
[拒绝的替代方案] 配置文件指定单一 backend（被拒：缺乏弹性）
[影响范围] ACLController / 三 backend
[相关FDR] -
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
```

## FDR-M-C05-003 subprocess 安全约束

```
[决策编号] FDR-M-C05-003
[决策标题] backend 内部 subprocess 强制 list 形式 + timeout 10s
[决策状态] 已接受
[决策内容] IptablesBackend / IpsetBackend 的 _run_* 方法仅接受 list[str] 参数，禁 shell 拼接
[决策理由] [TD:S-026] 禁止 shell 注入；CS-001 外部调用必须 timeout
[拒绝的替代方案] shell=True + str 拼接（被拒：注入风险）
[影响范围] iptables.py / ipset.py
[相关FDR] -
[来源标注] [DD-001:TD:S-026/CS-001]
```

**FDR 覆盖率: 100%（3/3 关键决策已记录）**
