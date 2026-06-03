# 文件框架结构 FF-M-C05-MCP-V1.0-20260602

```
[模块编号] M-C05
[模块名称] Network ACL
[文件框架]
  src/agenthub/infrastructure/network_acl/
    __init__.py              ← 模块初始化（导出 ACLController / ACLBackend / 三后端 / ACLRule / MODULE_VERSION）
    controller.py            ← ACLController（FastAPI router + 编排）+ ACLRule 模型 + 异常类
      - ACLRule（pydantic BaseModel，Drafted→Applied→Revoked 状态机）
      - ACLController（apply/revoke/_select_backend）
      - ACLBackendUnavailable(503) / ACLConflict(409)
    backends/
      __init__.py            ← 子包导出
      base.py                ← ACLBackend ABC（Strategy + Adapter 模式核心）
        - apply(rules)/revoke(rule_id)/healthcheck()
      iptables.py            ← IptablesBackend（主机层 subprocess 封装，timeout 10s）
      docker_network.py      ← DockerNetworkBackend（aiodocker 客户端，容器化 ws）
      ipset.py               ← IpsetBackend（大量 CIDR 集合）
    tests/
      __init__.py            ← 测试包标识
      test_controller.py     ← 9 用例（apply/幂等/冲突/backend 切换/revoke/串行/性能）
      test_backends.py       ← 9 用例（三后端 apply/revoke/healthcheck + 切换）
[文件间依赖关系]
  controller.py → backends/base.py → {iptables,docker_network,ipset}.py
  backends/*.py → backends/base.py
  tests/test_*.py → controller.py + backends/*
  外部依赖: agenthub.core.{config,exceptions,logging}
  反向依赖（仅声明）: agenthub.application.binding（M-B03 调用，[DD-M推断]）
[依赖无循环] ✓
[命名合规] snake_case 文件 / PascalCase 类 / 双引号 / 4 空格
[来源标注] [DD-001:FS-014/MD-MCP-V1.0-20260602#M-C05]
[DD-M洞察]
  1. MD 提及 rules/applier 子模块但 FS-014 未列，遵循 FS 仅在 controller.py 内含 ACLRule 模型——避免模块边界文件膨胀
  2. 三 backend 的 apply 必须 timeout 10s（CS-001 外部调用超时约束）+ 禁止 shell 拼接（[TD:S-026]）
  3. backend 切换属 Strategy 选择，参考 M-C01 SandboxFactory 探测模式（OS / 容器环境）
[阶梯退出检查]
  ① 全部目录已创建: 是 ② 全部文件已创建: 是 ③ 命名合规: 是 ④ D2:100%
```

**D2 = 100% | 5/5 合规项通过**
