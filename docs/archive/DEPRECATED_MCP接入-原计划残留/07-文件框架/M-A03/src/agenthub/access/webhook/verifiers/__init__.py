"""M-A03 verifiers 子包入口.

[文件路径] src/agenthub/access/webhook/verifiers/__init__.py
[文件职责] 导出 HMACVerifier 抽象与各 source 实现
[所属模块] M-A03（来自DD-001）
[关联设计规范] FS-003 / MD-M-A03（来自DD-001）
[功能描述]
  功能1: 导出 HMACVerifier ABC
  功能2: 导出 GitHubVerifier / GitLabVerifier / BitbucketVerifier
[输入输出]
  输入: 无
  输出: 包级符号
[依赖关系]
  依赖文件: base.py / github.py / gitlab.py / bitbucket.py
  被依赖文件: webhook.__init__ / app.py
[注意事项]
  注意1: 任何新增 source 必须继承 HMACVerifier 并实现 verify
[代码风格] 遵循CS-MCP-V1.0
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A03-20260603 - 初始版本
[作者] DD-M-A03-20260603
[来源标注] [DD-001:FS-003 + MD-M-A03]
"""

from agenthub.access.webhook.verifiers.base import HMACVerifier
from agenthub.access.webhook.verifiers.bitbucket import BitbucketVerifier
from agenthub.access.webhook.verifiers.github import GitHubVerifier
from agenthub.access.webhook.verifiers.gitlab import GitLabVerifier

__all__: list[str] = [
    "HMACVerifier",
    "GitHubVerifier",
    "GitLabVerifier",
    "BitbucketVerifier",
]
