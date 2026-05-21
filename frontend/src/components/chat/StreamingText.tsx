import type { ChatMessage } from "@/types";

interface Props {
  message: ChatMessage;
}

/** 单条消息气泡；streaming 时显示光标。 */
export function StreamingText({ message }: Props) {
  return (
    <div className={`bubble bubble-${message.role}`}>
      <span className="bubble-content">{message.content}</span>
      {message.streaming && <span className="cursor">▋</span>}
    </div>
  );
}
