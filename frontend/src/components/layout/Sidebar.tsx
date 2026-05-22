import { useEffect } from "react";
import { useAgentStore } from "@/stores/agentStore";
import { SessionList } from "@/components/chat/SessionList";
import type { Agent, Session } from "@/types";

interface Props {
  onSelectAgent: (agent: Agent) => void;
  onSelectSession?: (s: Session) => void;
  activeAgentId: string | null;
  activeSessionId?: string | null;
}

export function Sidebar({
  onSelectAgent,
  onSelectSession,
  activeAgentId,
  activeSessionId,
}: Props) {
  const { agents, loading, load } = useAgentStore();

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <aside className="sidebar">
      <div className="sidebar-title">AgentHub</div>

      <div className="sidebar-section">会话</div>
      {onSelectSession && (
        <SessionList activeId={activeSessionId ?? null} onSelect={onSelectSession} />
      )}

      <div className="sidebar-section">Agents</div>
      {loading && <p className="hint">Loading...</p>}
      {!loading && agents.length === 0 && (
        <p className="hint">No agents yet</p>
      )}
      <ul className="agent-list">
        {agents.map((a) => (
          <li
            key={a.id}
            className={a.id === activeAgentId ? "active" : ""}
            onClick={() => onSelectAgent(a)}
          >
            <span className="agent-avatar">{a.name.slice(0, 1)}</span>
            <span className="agent-meta">
              <span className="agent-name">{a.name}</span>
              <span className="agent-role">{a.role}</span>
            </span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
