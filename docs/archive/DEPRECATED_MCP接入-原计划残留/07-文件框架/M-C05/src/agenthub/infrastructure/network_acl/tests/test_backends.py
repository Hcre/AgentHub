"""M-C05 backends 单元测试.

[文件路径] src/agenthub/infrastructure/network_acl/tests/test_backends.py
[文件职责] 三 backend 实现 + Strategy 选择的测试
[所属模块] M-C05（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602#M-C05
[测试策略]
  用例数: 9
  覆盖: iptables / docker_network / ipset 各自的 apply/revoke/healthcheck
[来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# [测试场景1: IptablesBackend.apply 成功] [断言: subprocess exit=0，返回 rule_ids] [Mock: asyncio.create_subprocess_exec]
# [测试场景2: IptablesBackend.apply 超时] [断言: 抛 ACLBackendUnavailable] [Mock: subprocess 抛 TimeoutError]
# [测试场景3: IptablesBackend.revoke 成功] [断言: iptables -D 调用 1 次] [Mock: subprocess exit=0]
# [测试场景4: DockerNetworkBackend.healthcheck] [断言: aiodocker ping True] [Mock: aiodocker client]
# [测试场景5: DockerNetworkBackend.apply] [断言: aiodocker network acl 设置成功] [Mock: aiodocker]
# [测试场景6: IpsetBackend.apply CIDR] [断言: ipset -A 调用 N 次] [Mock: subprocess]
# [测试场景7: IpsetBackend.healthcheck] [断言: ipset list 退出码 0] [Mock: subprocess]
# [测试场景8: Backend 切换] [断言: iptables 不可用时 controller 切到 ipset] [Mock: IptablesBackend.healthcheck=False]
# [测试场景9: Backend 全部不可用] [断言: 抛 ACLBackendUnavailable 503] [Mock: 全部 healthcheck=False]
