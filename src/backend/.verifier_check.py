"""verifier 临时脚本：检查 DB 现状（不修改任何文件）。"""
import asyncio
from app.infrastructure.db.base import session_factory
from app.infrastructure.db.models import SessionModel, MessageModel, NotificationModel, TaskModel, AgentModel
from sqlalchemy import select, func


async def main():
    async with session_factory() as db:
        sess = (await db.execute(select(func.count(SessionModel.id)))).scalar()
        msg = (await db.execute(select(func.count(MessageModel.id)))).scalar()
        notif = (await db.execute(select(func.count(NotificationModel.id)))).scalar()
        task = (await db.execute(select(func.count(TaskModel.id)))).scalar()
        agt = (await db.execute(select(func.count(AgentModel.id)))).scalar()
        print(f"sessions={sess} messages={msg} notifications={notif} tasks={task} agents={agt}")

        # Demo session list
        from sqlalchemy import or_
        prefix = ('S1 -', 'S2 -', 'S3 -', 'S4 -', 'S5 -')
        rows = (await db.execute(
            select(SessionModel.id, SessionModel.title, SessionModel.type)
            .where(or_(*[SessionModel.title.like(f"{p}%") for p in prefix]))
            .order_by(SessionModel.title)
        )).all()
        print("\n--- demo sessions ---")
        for r in rows:
            print(f"  {r[1]} ({r[2]}) -> {r[0]}")

        # Inbox items
        rows = (await db.execute(
            select(NotificationModel.title, NotificationModel.category, NotificationModel.is_read)
            .where(NotificationModel.category.in_(['inbox_approval', 'inbox_approved']))
        )).all()
        print("\n--- inbox notifications ---")
        for r in rows:
            print(f"  [{r[1]} read={r[2]}] {r[0]}")

        # Tasks
        rows = (await db.execute(
            select(TaskModel.title, TaskModel.status)
        )).all()
        print("\n--- tasks ---")
        for r in rows:
            print(f"  [{r[1]}] {r[0]}")


asyncio.run(main())
