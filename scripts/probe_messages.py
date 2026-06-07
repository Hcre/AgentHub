#!/usr/bin/env python
"""Check S2 group messages and S3 private messages content."""
import urllib.request
import json

def get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.loads(r.read())

print("=== S2 group messages (d0583dfd) ===")
try:
    d = get("http://127.0.0.1:8000/api/sessions/d0583dfd-2f1c-45ae-9e89-6c1ec8b367e0/messages")
    print(f"count: {len(d)}")
    for m in d[:8]:
        role = m.get("role", "?")
        ct = m.get("content_type", m.get("type", "?"))
        who = m.get("who", m.get("agent_id", ""))
        text = (m.get("content") or m.get("text") or "")
        print(f"  role={role:10s} ct={ct:14s} who={who[:8] if who else '-':8s} text={text[:100]!r}")
except Exception as e:
    print(f"err: {e}")

print("\n=== S3 private messages (6c2f7d24) ===")
try:
    d = get("http://127.0.0.1:8000/api/sessions/6c2f7d24-c47d-4b50-ab19-d5fd6f3fe824/messages")
    print(f"count: {len(d)}")
    for m in d[:8]:
        role = m.get("role", "?")
        ct = m.get("content_type", m.get("type", "?"))
        text = (m.get("content") or m.get("text") or "")
        print(f"  role={role:10s} ct={ct:14s} text={text[:200]!r}")
except Exception as e:
    print(f"err: {e}")

print("\n=== Groups ===")
try:
    d = get("http://127.0.0.1:8000/api/groups")
    groups = d if isinstance(d, list) else d.get("items", [])
    print(f"count: {len(groups)}")
    for g in groups[:8]:
        gid = g.get("id", "?")[:8]
        nm = g.get("name") or g.get("title") or "?"
        mems = len(g.get("member_ids", g.get("members", [])))
        coord = g.get("coordinator_id", "?")[:8] if g.get("coordinator_id") else "-"
        print(f"  {gid}..  name={nm:30s}  members={mems}  coord={coord}..")
except Exception as e:
    print(f"err: {e}")
