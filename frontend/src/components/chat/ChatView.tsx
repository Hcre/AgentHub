import { useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { MessageList } from "@/components/chat/MessageList";
import { MessageInput } from "@/components/chat/MessageInput";

interface Props {
  sessionId: string | null;
  title: string;
}

export function ChatView({ sessionId, title }: Props) {
  const { sendMessage } = useWebSocket(sessionId);
  const connected = useChatStore((s) => s.connected);
  const reset = useChatStore((s) => s.reset);

  useEffect(() => {
    reset();
  }, [sessionId, reset]);

  if (!sessionId) {
    return (
      <div className="chat-view empty">
        <p>选择左侧 Agent 创建私聊会话</p>
      </div>
    );
  }

  return (
    <div className="chat-view">
      <header className="chat-header">
        <span>{title}</span>
        <span className={`status-dot ${connected ? "online" : "offline"}`} />
      </header>
      <MessageList />
      <MessageInput onSend={sendMessage} />
    </div>
  );
}
