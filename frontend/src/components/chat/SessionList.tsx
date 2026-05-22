import { useState, useEffect, useMemo } from "react";
import type { Session } from "@/types";
import { sessionsApi } from "@/api/sessions";

interface Props {
  activeId: string | null;
  onSelect: (s: Session) => void;
}

export function SessionList({ activeId, onSelect }: Props) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [search, setSearch] = useState("");

  const load = () => {
    sessionsApi.list().then(setSessions).catch(() => {});
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return sessions;
    const q = search.toLowerCase();
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, search]);

  return (
    <div className="session-list">
      <div className="session-search">
        <input
          type="text"
          placeholder="搜索会话..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <ul>
        {filtered.map((s) => (
          <li
            key={s.id}
            className={s.id === activeId ? "active" : ""}
            onClick={() => onSelect(s)}
          >
            <span className="session-icon">{s.type === "private" ? "@" : "#"}</span>
            <span className="session-title">{s.title || "未命名会话"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
