import asyncio, json
from app.infrastructure.db.base import get_session
from sqlalchemy import text

async def main():
    async for session in get_session():
        # Read all agents
        r = await session.execute(text("SELECT id, name, settings FROM agents WHERE is_deleted = false"))
        agents = [(row[0], row[1], row[2] or {}) for row in r.fetchall()]

        updated = 0
        for agent_id, name, settings in agents:
            mode = settings.get("permission_mode", "acceptEdits")
            if mode != "bypassPermissions":
                settings["permission_mode"] = "bypassPermissions"
                await session.execute(
                    text("UPDATE agents SET settings = :s WHERE id = :id"),
                    {"s": json.dumps(settings), "id": agent_id}
                )
                updated += 1
                print(f"  Fixed: {name} ({mode} → bypassPermissions)")

        await session.commit()
        print(f"Updated {updated} agents")
        break

asyncio.run(main())
