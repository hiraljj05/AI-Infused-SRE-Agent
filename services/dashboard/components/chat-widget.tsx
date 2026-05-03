"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MessageCircle, Send, Sparkles, X, Trash2 } from "lucide-react";
import { api } from "@/lib/api";

type Msg = {
  id: string;
  role: "user" | "agent";
  content: string;
  citations?: string[];
  model?: string;
  ts: Date;
  error?: boolean;
};

const SUGGESTIONS = [
  "What is broken right now?",
  "Show recent incidents on payments-api",
  "Who owns orders-api?",
  "How do I debug a CrashLoopBackOff?",
];

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function fmt(d: Date) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [msgs, loading, open]);

  useEffect(() => {
    if (taRef.current) {
      taRef.current.style.height = "auto";
      taRef.current.style.height = `${Math.min(taRef.current.scrollHeight, 140)}px`;
    }
  }, [input]);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setMsgs((m) => [...m, { id: uid(), role: "user", content: q, ts: new Date() }]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.ask(q);
      setMsgs((m) => [
        ...m,
        {
          id: uid(),
          role: "agent",
          content: res.answer,
          citations: res.cited_docs,
          model: res.model,
          ts: new Date(),
        },
      ]);
    } catch (e) {
      setMsgs((m) => [
        ...m,
        {
          id: uid(),
          role: "agent",
          content: `Something went wrong: ${(e as Error).message}`,
          ts: new Date(),
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <>
      {/* Floating launcher button --------------------------------- */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Ask the SRE Agent"
          className="group fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full text-white transition-transform hover:scale-105"
          style={{
            background: "var(--grad-brand)",
            boxShadow: "var(--shadow-md)",
          }}
        >
          <MessageCircle size={22} strokeWidth={2.2} />
          <span className="absolute -top-1 -right-1 flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-white" />
          </span>
        </button>
      )}

      {/* Drawer ---------------------------------------------------- */}
      {open && (
        <div
          className="fixed bottom-6 right-6 z-40 flex w-[380px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl animate-slide-up sm:w-[420px]"
          style={{ height: "min(640px, calc(100vh - 48px))" }}
        >
          {/* Header */}
          <div
            className="flex items-center gap-3 px-4 py-3 text-white"
            style={{ background: "var(--grad-brand)" }}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/20 backdrop-blur">
              <Sparkles size={16} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold leading-tight font-sans">CentrifyAI</div>
              <div className="flex items-center gap-1.5 text-[10.5px] text-white/80 font-sans">
                <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-emerald-300" />
                Online · runbooks, incidents, services
              </div>
            </div>
            <button
              onClick={() => msgs.length && confirm("Clear chat?") && setMsgs([])}
              className="rounded-md p-1.5 text-white/70 transition hover:bg-white/10 hover:text-white disabled:opacity-30"
              disabled={msgs.length === 0}
              title="Clear conversation"
            >
              <Trash2 size={14} />
            </button>
            <button
              onClick={() => setOpen(false)}
              className="rounded-md p-1.5 text-white/80 transition hover:bg-white/10 hover:text-white"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            className="scrollbar-thin flex-1 space-y-3 overflow-y-auto bg-slate-50/50 px-3 py-3"
          >
            {msgs.length === 0 && !loading && (
              <div className="px-1 py-3 text-center">
                <div
                  className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl text-white"
                  style={{ background: "var(--grad-brand)" }}
                >
                  <Sparkles size={20} />
                </div>
                <div className="text-sm font-semibold text-slate-900 font-sans">
                  How can I help?
                </div>
                <div className="mb-3 mt-1 text-[12px] text-slate-500 font-sans">
                  Ask anything about your incidents, services, runbooks or SLOs.
                </div>
                <div className="flex flex-col gap-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-[12px] text-slate-700 transition hover:border-brand-300 hover:bg-brand-50/40 hover:text-brand-700 font-sans"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {msgs.map((m) => (
              <Bubble key={m.id} m={m} />
            ))}

            {loading && (
              <div className="flex items-start gap-2">
                  <div
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
                    style={{ background: "var(--grad-brand)" }}
                  >
                  <Sparkles size={12} />
                </div>
                <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-3 py-2.5">
                  <div className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="border-t border-slate-200 bg-white p-2.5">
            <div className="flex items-end gap-1.5 rounded-xl border border-slate-200 bg-white px-2 py-1.5 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
              <textarea
                ref={taRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder="Ask about incidents, runbooks…"
                disabled={loading}
                className="max-h-[140px] flex-1 resize-none bg-transparent px-1 py-1 text-[13px] outline-none placeholder:text-slate-400 disabled:opacity-50 font-sans"
              />
              <button
                onClick={() => send()}
                disabled={loading || !input.trim()}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white transition disabled:opacity-30"
                style={{ background: "var(--grad-brand)" }}
                aria-label="Send"
              >
                <Send size={14} />
              </button>
            </div>
            <div className="mt-1 px-1 text-[10px] text-slate-400 font-sans">
              Enter to send · Shift+Enter for new line
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Bubble({ m }: { m: Msg }) {
  const isUser = m.role === "user";
  return (
    <div className={`flex items-start gap-2 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${
          isUser
            ? "bg-slate-200 text-slate-700"
            : "text-white"
        }`}
        style={!isUser ? { background: "var(--grad-brand)" } : undefined}
      >
        {isUser ? "YOU" : <Sparkles size={12} />}
      </div>
      <div className={`max-w-[82%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`rounded-2xl px-3 py-2 text-[13px] leading-relaxed font-sans ${
            isUser
              ? "rounded-tr-sm bg-brand-600 text-white"
              : m.error
                ? "rounded-tl-sm border border-rose-200 bg-rose-50 text-rose-700"
                : "rounded-tl-sm border border-slate-200 bg-white text-slate-800"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{m.content}</p>
          ) : (
            <div className="markdown-body text-[13px]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            </div>
          )}
        </div>
        <div
          className={`mt-1 flex items-center gap-2 text-[10px] text-slate-400 ${
            isUser ? "justify-end" : ""
          }`}
        >
          <span>{fmt(m.ts)}</span>
          {!isUser && m.model && (
            <>
              <span>·</span>
              <span className="text-mono">{m.model.split("/").pop()}</span>
            </>
          )}
        </div>
        {m.citations && m.citations.length > 0 && (
          <div
            className={`mt-1.5 flex flex-wrap gap-1 ${isUser ? "justify-end" : ""}`}
          >
            {m.citations.map((c) => (
              <span
                key={c}
                title="Source"
                className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-mono text-[9.5px] text-slate-500"
              >
                {c}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
