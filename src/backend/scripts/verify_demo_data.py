"""Verify seed data via API."""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def get_json(path):
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read())


def main():
    agents = get_json("/api/agents")
    sessions = get_json("/api/sessions")
    groups = get_json("/api/groups")
    inbox = get_json("/api/inbox")

    print(f"=== /api/agents ({len(agents)}) ===")
    for a in agents:
        print(f"  - {a['name']:20s} {a['agent_system']:12s} role={a.get('role', '')[:40]}")

    print(f"\n=== /api/sessions ({len(sessions)}) ===")
    for s in sessions:
        stype = s.get("type", "?")
        sid = s.get("id", "")
        print(f"  - [{stype}] {s['title']:30s} (id={sid[:8]})")

    print(f"\n=== /api/groups ({len(groups)}) ===")
    for g in groups:
        print(f"  - {g['name']:30s} coordinator={g.get('coordinator_id', '?')[:8]}")

    print(f"\n=== /api/inbox ({len(inbox.get('items', []))}) ===")
    for it in inbox.get("items", []):
        print(f"  - [{it.get('category', '?')}] {it.get('title', '')}")

    # Check story-specific sessions
    print("\n=== 5 Core User Story Sessions ===")
    target_titles = [
        "S1 - 重构 pricing 页",
        "S2 - 营销页升级",
        "S3 - 提案预览",
        "S4 - 与 MyBot 试用",
    ]
    for tt in target_titles:
        match = [s for s in sessions if s.get("title") == tt]
        if not match:
            print(f"  ❌ MISSING: {tt}")
            continue
        sid = match[0]["id"]
        try:
            msgs = get_json(f"/api/sessions/{sid}/messages")
        except Exception as e:
            print(f"  ⚠ {tt}: cannot fetch messages ({e})")
            continue
        has_code = any("```" in m.get("content", "") for m in msgs)
        has_diff = any(m.get("content_type") == "diff" for m in msgs)
        has_url = any("https://" in m.get("content", "") for m in msgs)
        flags = []
        if has_code:
            flags.append("CODE")
        if has_diff:
            flags.append("DIFF")
        if has_url:
            flags.append("URL")
        print(f"  ✅ {tt:25s} msgs={len(msgs):2d}  flags={','.join(flags) or '-'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
