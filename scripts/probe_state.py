#!/usr/bin/env python
"""Probe AgentHub API to understand current state for video script."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=3) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


print("=== Health ===")
print(get("/health"))

print("\n=== Agents ===")
status, body = get("/api/agents")
print(f"status={status}")
try:
    d = json.loads(body)
    agents = d if isinstance(d, list) else d.get("items", [])
    print(f"total agents: {len(agents)}")
    for a in agents[:15]:
        nm = a.get("display_name") or a.get("name") or "?"
        print(f"  {nm:20s}  kind={a.get('kind','?'):10s}  id={(a.get('id') or '?')[:8]}")
except Exception as e:
    print(f"err: {e}")
    print(body[:300])

print("\n=== Sessions ===")
status, body = get("/api/sessions")
print(f"status={status}")
try:
    d = json.loads(body)
    sessions = d if isinstance(d, list) else d.get("items", [])
    print(f"total sessions: {len(sessions)}")
    for s in sessions[:15]:
        sid = s.get("id", "?")[:8]
        kind = s.get("kind", "?")
        title = (s.get("title") or "?")[:50]
        print(f"  {sid}..  kind={kind:10s}  title={title}")
except Exception as e:
    print(f"err: {e}")

print("\n=== Inbox ===")
status, body = get("/api/inbox")
print(f"status={status}")
print(body[:400])

print("\n=== Tasks ===")
status, body = get("/api/tasks")
print(f"status={status}")
print(body[:300])
