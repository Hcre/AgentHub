import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/chatStore";
import { MessageBubble } from "@/components/chat/MessageBubble";

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.length === 0 && (
        <p className="empty-hint">Start chatting with an Agent</p>
      )}
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
