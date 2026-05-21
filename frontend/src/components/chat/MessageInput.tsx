import { useState, type KeyboardEvent } from "react";
import { useChatStore } from "@/stores/chatStore";

interface Props {
  onSend: (content: string) => void;
}

export function MessageInput({ onSend }: Props) {
  const [value, setValue] = useState("");
  const connected = useChatStore((s) => s.connected);

  const submit = () => {
    const text = value.trim();
    if (!text) return;
    onSend(text);
    setValue("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="message-input">
      <textarea
        value={value}
        placeholder={connected ? "输入消息，Enter 发送…" : "连接中…"}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        rows={2}
      />
      <button onClick={submit} disabled={!connected || !value.trim()}>
        发送
      </button>
    </div>
  );
}
