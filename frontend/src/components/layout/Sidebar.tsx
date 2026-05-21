import { useEffect } from "react";
import { useAgentStore } from "@/stores/agentStore";
import type { Agent } from "@/types";

interface Props {
  onSelectAgent: (agent: Agent) => void;
  activeAgentId: string | null;
}

export function Sidebar({ onSelectAgent, activeAgentId }: Props) {
  const { agents, loading, load } = useAgentStore();

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <aside className="sidebar">
      <div className="sidebar-title">AgentHub</div>
      <div className="sidebar-section">Agents</div>
      {loading && <p className="hint">加载中…</p>}
      {!loading && agents.length === 0 && (
        <p className="hint">暂无 Agent，请先在后端创建</p>
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
