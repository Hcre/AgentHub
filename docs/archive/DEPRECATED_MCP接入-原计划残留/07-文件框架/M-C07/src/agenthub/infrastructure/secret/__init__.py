"""M-C07 Secret Manager 包初始化.

[文件路径] src/agenthub/infrastructure/secret/__init__.py
[文件职责] 暴露 Secret Manager 公共接口（VaultClient / TokenManager / SecretCache / Transit）
[所属模块] M-C07
[关联设计规范] FS-016 (FS-MCP-V1.0) / MD-M-C07 (MD-MCP-V1.0) / IC-014 (IC-MCP-V1.0) / CS-MCP-V1.0 §1
[功能描述]
  功能1: 集中导出 VaultClient、TokenManager、Transit、SecretCache 四个核心类
  功能2: 屏蔽 Vault SDK 内部细节，对外只暴露 4 个语义化入口（get/put/encrypt/decrypt）
  功能3: 统一异常映射（VaultSealed/PermissionDenied/RateLimit 转化为领域异常）
[输入输出]
  输入: 上游调用方（创建 token 后的所有业务模块）传入 path/value 或 plaintext/ciphertext
  输出: 字节流或封装为领域 DTO（SecretValue、EncryptedBlob）
[依赖关系]
  依赖文件: vault_client.py / token_manager.py / transit.py / cache.py
  被依赖文件: core.config (Settings 注入 Vault 地址) / 各业务模块（M-B05 create 流程、M-A03 webhook 等）
[注意事项]
  注意1: 本包在启动时必须完成 Vault 健康探测（fail-fast），未就绪则拒绝启动
  注意2: 不得在模块导入阶段连接 Vault；所有 IO 在 async 上下文执行
  注意3: 严禁打印或日志泄露 secret 明文；structlog 配置中 secret 字段已 redact
  注意4: 缓存使用 in-proc LRU 30s TTL，跨进程不共享——若需要集群级缓存由 M-D03 接管
[代码风格] 遵循 CS-MCP-V1.0 §1（Python 3.11 + Google docstring + 4 空格缩进 + 类型注解强制）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C07 - 初始框架，仅含注释与导出占位
[作者] DD-M-C07-20260603
[来源标注] [DD-001:FS-016/MD-M-C07/IC-014]
"""

# ----------------------------------------------------------------------
# 公共接口导出（延迟到具体实现落地后由 DD-S/Dev 填充）
# ----------------------------------------------------------------------
# from agenthub.infrastructure.secret.vault_client import VaultClient
# from agenthub.infrastructure.secret.token_manager import TokenManager
# from agenthub.infrastructure.secret.transit import Transit
# from agenthub.infrastructure.secret.cache import SecretCache

# __all__ = [
#     "VaultClient",
#     "TokenManager",
#     "Transit",
#     "SecretCache",
#     # 领域异常（已定义于 core.exceptions，透传）
#     "VaultSealed",
#     "VaultPermissionDenied",
#     "VaultRateLimited",
# ]
