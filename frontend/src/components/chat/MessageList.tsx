import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/chatStore";
import { StreamingText } from "@/components/chat/StreamingText";

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.length === 0 && (
        <p className="empty-hint">开始与 Agent 对话吧</p>
      )}
      {messages.map((m) => (
        <StreamingText key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
