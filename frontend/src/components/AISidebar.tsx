"use client";

import { useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import type { ChatMessage } from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

interface AISidebarProps {
  board: BoardData;
  onBoardUpdate: (board: BoardData) => void;
  isOpen: boolean;
  onClose: () => void;
}

export const AISidebar = ({ board: _board, onBoardUpdate, isOpen, onClose }: AISidebarProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const history = messages;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    try {
      const result = await api.aiChat(text, history);
      setMessages((prev) => [...prev, { role: "assistant", content: result.reply }]);
      onBoardUpdate(result.board);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 z-50 flex h-screen w-96 flex-col border-l border-[var(--stroke)] bg-white shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--stroke)] px-6 py-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
            AI Assistant
          </p>
          <h2 className="mt-1 font-display text-xl font-semibold text-[var(--navy-dark)]">
            Board Chat
          </h2>
        </div>
        <button
          onClick={onClose}
          aria-label="Close AI sidebar"
          className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--secondary-purple)] hover:text-[var(--secondary-purple)]"
        >
          Close
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <p className="mt-8 text-center text-sm text-[var(--gray-text)]">
            Ask me to create, move, or delete cards on your board.
          </p>
        )}
        <div className="flex flex-col gap-3">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={msg.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  msg.role === "user"
                    ? "max-w-[80%] rounded-2xl rounded-tr-sm bg-[var(--primary-blue)] px-4 py-3 text-sm text-white"
                    : "max-w-[80%] rounded-2xl rounded-tl-sm border border-[var(--accent-yellow)] bg-[#fef9ec] px-4 py-3 text-sm text-[var(--navy-dark)]"
                }
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-tl-sm border border-[var(--accent-yellow)] bg-[#fef9ec] px-4 py-3 text-sm text-[var(--gray-text)]">
                Thinking...
              </div>
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-[var(--stroke)] px-6 py-4">
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
            disabled={loading}
            placeholder="Ask the AI..."
            aria-label="AI chat input"
            className="flex-1 rounded-xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-sm outline-none transition focus:border-[var(--primary-blue)] disabled:opacity-50"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="rounded-xl bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};
