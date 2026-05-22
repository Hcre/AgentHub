import type { ChatMessage } from "@/types";

interface Props {
  message: ChatMessage;
}

const roleLabel: Record<string, string> = {
  user: "You",
  assistant: "Agent",
  system: "System",
};

export function MessageBubble({ message }: Props) {
  const cls = `bubble bubble-${message.role}`;
  const isStreaming = message.streaming;

  return (
    <div className={cls}>
      {message.role !== "user" && (
        <span className="bubble-label">{roleLabel[message.role]}</span>
      )}
      <span className="bubble-text">
        {message.content}
        {isStreaming && <span className="cursor">|</span>}
      </span>
      {message.contentType === "code" && (
        <span className="bubble-code-badge">CODE</span>
      )}
    </div>
  );
}
