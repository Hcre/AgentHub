"""M-A01 Web API Gateway package.

[文件路径] src/agenthub/access/api_gateway/__init__.py
[文件职责] M-A01 包初始化，导出 GatewayApp 公共入口
[所属模块] M-A01 Web API Gateway
[关联设计规范] FS-001 / MD:M-A01
[功能描述]
  功能1: 暴露 GatewayApp 单例工厂作为对外公共接口
  功能2: 注册子模块（controllers / middleware / schemas）
[输入输出]
  输入: 无（包初始化无运行时输入）
  输出: get_app() → GatewayApp 实例
[依赖关系]
  依赖文件: app.py
  被依赖文件: deploy/docker/Dockerfile（uvicorn 启动入口）
[注意事项]
  注意1: 禁止在此文件做重逻辑导入，避免循环依赖（[DD-001:CS §1.5]）
  注意2: __all__ 必须显式声明对外符号，禁止 *
[代码风格] 遵循 CS-MCP-V1.0 §1（Python 3.11 / 4 空格 / Google docstring）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A01 - 初版（仅注释骨架，无业务代码）
[作者] DD-M-A01-20260603
[来源标注] [DD-001:FS-001 + MD:M-A01]
"""

from __future__ import annotations

# [DD-M-A01推断:依据 CS §1.5 显式 __all__] 仅在 app.py 实现后开放
__all__: list[str] = [
    # "GatewayApp",   # 由 app.py 提供
    # "get_app",      # 由 app.py 提供
]
