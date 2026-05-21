import { useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatView } from "@/components/chat/ChatView";
import { sessionsApi } from "@/api/sessions";
import type { Agent } from "@/types";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<Agent | null>(null);

  const onSelectAgent = async (agent: Agent) => {
    setActiveAgent(agent);
    // MVP：每次选中 Agent 即开一个私聊会话
    const session = await sessionsApi.createPrivate(agent.id, agent.name);
    setSessionId(session.id);
  };

  return (
    <div className="app">
      <Sidebar
        onSelectAgent={onSelectAgent}
        activeAgentId={activeAgent?.id ?? null}
      />
      <main className="main">
        <ChatView sessionId={sessionId} title={activeAgent?.name ?? "AgentHub"} />
      </main>
    </div>
  );
}
