"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Loader2 } from "lucide-react"
import { api, type Message } from "@/lib/api"
import { cn } from "@/lib/utils"

const SUGGESTED = [
  "What's my total return?",
  "Which stocks are dragging my portfolio down?",
  "How diversified am I across sectors?",
  "What's my biggest position?",
]

export function ChatPanel() {
  const [messages,        setMessages]        = useState<Message[]>([])
  const [input,           setInput]           = useState("")
  const [loading,         setLoading]         = useState(false)
  const [conversationId,  setConversationId]  = useState<string | undefined>()
  const [error,           setError]           = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg: Message = {
      id: crypto.randomUUID(), role: "user", content: trimmed, created_at: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setLoading(true)
    setError(null)

    try {
      const res = await api.sendMessage(trimmed, conversationId)
      setConversationId(res.conversation_id)
      setMessages(prev => [...prev, res.message])
    } catch (err: any) {
      setError(err.message ?? "Something went wrong. Please try again.")
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="card flex flex-col h-[600px]">
      {/* Header */}
      <div className="px-5 py-4 border-b border-surface-border flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-accent-dim flex items-center justify-center">
          <Bot className="w-4 h-4 text-accent" />
        </div>
        <div>
          <h3 className="text-sm font-semibold">Portfolio Analyst</h3>
          <p className="text-xs text-text-muted">Ask anything about your holdings</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-5 text-center">
            <div className="w-12 h-12 rounded-2xl bg-accent-dim flex items-center justify-center">
              <Bot className="w-6 h-6 text-accent" />
            </div>
            <div>
              <p className="text-sm font-medium mb-1">Ask me about your portfolio</p>
              <p className="text-xs text-text-muted">I can analyse returns, risk, sectors, and more</p>
            </div>
            <div className="grid grid-cols-1 gap-2 w-full max-w-xs">
              {SUGGESTED.map(q => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="text-left text-xs px-3 py-2.5 rounded-lg border border-surface-border
                             text-text-secondary hover:text-text-primary hover:border-accent/30
                             hover:bg-accent-dim transition-all duration-150"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={cn("flex gap-3", msg.role === "user" ? "flex-row-reverse" : "flex-row")}>
            <div className={cn(
              "w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
              msg.role === "user"
                ? "bg-surface border border-surface-border"
                : "bg-accent-dim"
            )}>
              {msg.role === "user"
                ? <User className="w-3.5 h-3.5 text-text-secondary" />
                : <Bot  className="w-3.5 h-3.5 text-accent" />
              }
            </div>
            <div className={cn(
              "max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed",
              msg.role === "user"
                ? "bg-surface-hover text-text-primary rounded-tr-sm"
                : "bg-surface border border-surface-border text-text-primary rounded-tl-sm"
            )}>
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-lg bg-accent-dim flex items-center justify-center shrink-0 mt-0.5">
              <Bot className="w-3.5 h-3.5 text-accent" />
            </div>
            <div className="bg-surface border border-surface-border rounded-2xl rounded-tl-sm px-4 py-3">
              <Loader2 className="w-4 h-4 text-accent animate-spin" />
            </div>
          </div>
        )}

        {error && (
          <p className="text-xs text-loss text-center bg-lossDim px-3 py-2 rounded-lg">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-surface-border">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your portfolio…"
            rows={1}
            disabled={loading}
            className="flex-1 bg-surface border border-surface-border rounded-xl px-4 py-2.5
                       text-sm text-text-primary placeholder:text-text-muted resize-none
                       focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20
                       transition-colors disabled:opacity-50 leading-5"
            style={{ maxHeight: "120px" }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center shrink-0
                       hover:bg-accent-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4 text-surface" />
          </button>
        </div>
        <p className="text-[10px] text-text-muted mt-1.5 px-1">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  )
}
