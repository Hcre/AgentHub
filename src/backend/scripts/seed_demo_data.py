"""Seed 5 个 Core User Story 的 demo 数据集到数据库。

用法:
    cd src/backend
    python scripts/seed_demo_data.py

幂等策略：先按 ``demo_tag`` 标记清理已有 demo 行，再创建新的。
- agents.settings['demo_tag'] == 'demo_p0_6'
- messages.extra['demo_tag'] == 'demo_p0_6'
- inbox / task 无 tag 字段 → 按 name / title 前缀（S1- / S2- / S3- / S4- / S5-）清理
- group / session 按 title 前缀清理（cascade 删除 messages / members）

退出码: 0=成功, 1=失败
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

# 让脚本能 import app.*
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

# 静默 SQLAlchemy INFO 日志（INSERT/SELECT 噪音太大）
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from sqlalchemy import delete, select  # noqa: E402

from app.data.demo_stories import DEMO_TAG, DEMO_USER_ID, create_all_stories  # noqa: E402
from app.infrastructure.db.base import engine, session_factory  # noqa: E402
from app.infrastructure.db.models import (  # noqa: E402
    AgentModel,
    GroupModel,
    MessageModel,
    NotificationModel,
    SessionModel,
    TaskModel,
)

# 关掉 engine echo（直接生效，不用反复 setLevel logger）
engine.echo = False
for _name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(_name).setLevel(logging.WARNING)

# 各 Story 的标题前缀，用于清理 inbox/task/group/session（这些表没有 demo_tag 字段）
# - group/session 标题格式: "S1 - xxx"（"-" 分隔符）
# - task 标题格式: "S1 xxx"（无分隔符，紧贴标题）
STORY_TITLE_PREFIXES = ("S1 -", "S2 -", "S3 -", "S4 -", "S5 -")
STORY_TASK_PREFIXES = ("S1 ", "S2 ", "S3 ", "S4 ", "S5 ")


async def _cleanup_existing(db) -> dict[str, int]:
    """按 demo_tag / 标题前缀清理已存在的 demo 数据。

    顺序：先 messages（无 FK 引用，简单）→ sessions → groups（含 members 级联）
    → tasks → notifications → agents（settings.demo_tag）。
    返回各表清理的行数（仅供日志）。
    """
    cleared: dict[str, int] = {}

    # 1) messages：按 extra['demo_tag'] = DEMO_TAG
    # PG 走 JSONB 下标查询；SQLite 用 json_extract。
    # 为可移植，这里在 Python 层先查 sessions.id 再按 session_id 删。
    # 先找所有 demo session 的 id。
    stmt_sessions = select(SessionModel.id).where(
        SessionModel.title.like(tuple(f"{p}%" for p in STORY_TITLE_PREFIXES)[0])
    )
    # tuple 不支持 like in —— 改用 OR 拼
    from sqlalchemy import or_

    stmt_sessions = select(SessionModel.id).where(
        or_(*[SessionModel.title.like(f"{p}%") for p in STORY_TITLE_PREFIXES])
    )
    session_ids = [row[0] for row in (await db.execute(stmt_sessions)).all()]

    if session_ids:
        # messages 走 session_id IN
        r = await db.execute(delete(MessageModel).where(MessageModel.session_id.in_(session_ids)))
        cleared["messages"] = r.rowcount or 0
        # sessions 自身
        r = await db.execute(delete(SessionModel).where(SessionModel.id.in_(session_ids)))
        cleared["sessions"] = r.rowcount or 0
    else:
        cleared["messages"] = 0
        cleared["sessions"] = 0

    # 2) groups：按 name 前缀
    stmt_groups = select(GroupModel.id).where(
        or_(*[GroupModel.name.like(f"{p}%") for p in STORY_TITLE_PREFIXES])
    )
    group_ids = [row[0] for row in (await db.execute(stmt_groups)).all()]
    if group_ids:
        # group_members 会通过 FK ondelete=CASCADE 自动清；这里显式删以防 SQLite
        r = await db.execute(delete(GroupModel).where(GroupModel.id.in_(group_ids)))
        cleared["groups"] = r.rowcount or 0
    else:
        cleared["groups"] = 0

    # 3) tasks：按 title 前缀（task 标题无 " -" 分隔符）
    stmt_tasks = select(TaskModel.id).where(
        or_(*[TaskModel.title.like(f"{p}%") for p in STORY_TASK_PREFIXES])
    )
    task_ids = [row[0] for row in (await db.execute(stmt_tasks)).all()]
    if task_ids:
        r = await db.execute(delete(TaskModel).where(TaskModel.id.in_(task_ids)))
        cleared["tasks"] = r.rowcount or 0
    else:
        cleared["tasks"] = 0

    # 4) notifications：demo user 下的 inbox_approval / inbox_approved
    #    按 title 前缀匹配（"【待审】" / "【已通过】" 都对应 demo 内容）
    stmt_notif = select(NotificationModel.id).where(
        NotificationModel.user_id == DEMO_USER_ID,
        NotificationModel.category.in_(["inbox_approval", "inbox_approved"]),
    )
    notif_ids = [row[0] for row in (await db.execute(stmt_notif)).all()]
    if notif_ids:
        r = await db.execute(delete(NotificationModel).where(NotificationModel.id.in_(notif_ids)))
        cleared["notifications"] = r.rowcount or 0
    else:
        cleared["notifications"] = 0

    # 5) agents：按 name 在 S1/S2/S3/S4 预设清单里
    demo_agent_names = [
        "Claude",
        "Coordinator",
        "Claude (S2)",
        "OpenCode (S2)",
        "MockBot (S2)",
        "Claude (S4)",
        "OpenCode (S4)",
        "Pi (S4)",
        "Codex (S4)",
        "MyBot",
    ]
    stmt_agents = select(AgentModel.id).where(AgentModel.name.in_(demo_agent_names))
    agent_ids = [row[0] for row in (await db.execute(stmt_agents)).all()]
    if agent_ids:
        r = await db.execute(delete(AgentModel).where(AgentModel.id.in_(agent_ids)))
        cleared["agents"] = r.rowcount or 0
    else:
        cleared["agents"] = 0

    await db.flush()
    return cleared


async def main() -> int:
    print("=" * 60)
    print("P0-6 Demo 数据集 Seed 脚本")
    print(f"  demo_tag = {DEMO_TAG}")
    print(f"  demo user = {DEMO_USER_ID}")
    print("=" * 60)

    try:
        async with session_factory() as db:
            # 1) 清理已有
            print("\n[1/3] 清理已有 demo 数据 ...")
            cleared = await _cleanup_existing(db)
            for tbl, n in cleared.items():
                print(f"  - {tbl}: {n} 行")
            await db.commit()

            # 2) 创建
            print("\n[2/3] 创建 5 个 Story 数据 ...")
            result = await create_all_stories(db)
            await db.commit()

            # 3) 汇总
            print("\n[3/3] Seed 完成:")
            print(f"  - agents:    {len(result['agents'])}")
            print(f"  - groups:    {len(result['groups'])}")
            print(f"  - sessions:  {len(result['sessions'])}")
            print(f"  - messages:  {len(result['messages'])}")
            print(f"  - inbox:     {len(result['inbox'])}")
            print(f"  - tasks:     {len(result['tasks'])}")

        print(f"\n✅ 已 seed {len(result['agents'])} 个 agent / "
              f"{len(result['sessions'])} 个 session / "
              f"{len(result['messages'])} 个 message")
        return 0

    except Exception as e:
        print(f"\n❌ Seed 失败: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
