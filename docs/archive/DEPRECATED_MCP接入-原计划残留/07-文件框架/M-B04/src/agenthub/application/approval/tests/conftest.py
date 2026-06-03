"""M-B04 Approval Engine — pytest 模块级 fixtures.

[文件路径] src/agenthub/application/approval/tests/conftest.py
[文件职责] 提供 fakeredis / asyncpg fixture / Mock UnitOfWork / Mock EventBus
[所属模块] M-B04
[关联设计规范] CS §1.7 测试规范
[功能描述]
  功能1: fakeredis client fixture（覆盖 AllowlistCache.redis）
  功能2: 内存 inbox_queue/inbox_decision Mock Repository
  功能3: spy EventBus（断言 publish 调用）
  功能4: 时间冻结 fixture（断言 5min 重放窗口、60s timeout）
[依赖关系] pytest / pytest-asyncio / pytest-mock / fakeredis
[注意事项]
  注意1: 所有 fixture 仅放本文件；测试文件禁止重复定义
  注意2: 异步 fixture 必须 @pytest_asyncio.fixture
[作者] DD-M-B04-20260603
[来源标注] [DD-001:CS §1.7 + DD-M-B04 推断: 模块级 fixture 集中管理]
"""

from __future__ import annotations

# Fixture 实现由 DD-S 阶段补全；本框架仅声明 fixture 列表：
# - fake_redis            (function-scoped)
# - mock_queue_repo       (function-scoped, in-memory list)
# - mock_decision_repo
# - mock_uow              (async context manager)
# - spy_event_bus         (records publish calls)
# - freeze_time           (monkeypatch datetime.now)
# - sample_check_request  (factory)
# - sample_decide_request (factory)
