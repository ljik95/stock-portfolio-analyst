"use client"

import { useState } from "react"
import { RefreshCw, LogOut, Bot } from "lucide-react"
import { usePortfolio } from "@/hooks/usePortfolio"
import { UploadZone }    from "@/components/dashboard/UploadZone"
import { SummaryCards }  from "@/components/dashboard/SummaryCards"
import { SectorChart }   from "@/components/dashboard/SectorChart"
import { HoldingsTable } from "@/components/dashboard/HoldingsTable"
import { InsightsPanel } from "@/components/dashboard/InsightsPanel"
import { PortfolioValueChart } from "@/components/dashboard/PortfolioValueChart"
import { ChatPanel }     from "@/components/chat/ChatPanel"

export default function Home() {
  const { state, summary, holdings, insights, history, error, importCSV, reload, reset } = usePortfolio()
  const [showChat, setShowChat] = useState(false)

  if (state === "idle" || state === "error") {
    return (
      <UploadZone
        onUpload={importCSV}
        loading={state === "idle" && false}
        error={error}
      />
    )
  }

  if (state === "loading" && !summary) {
    return (
      <div className="flex items-center justify-center min-h-screen gap-3 text-text-secondary">
        <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading portfolio…</span>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      {/* Top nav */}
      <header className="border-b border-surface-border sticky top-0 z-10 bg-surface/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-5 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center">
              <span className="text-surface font-bold text-xs">PA</span>
            </div>
            <span className="font-semibold text-sm">Portfolio Analyst</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowChat(c => !c)}
              className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors
                ${showChat
                  ? "bg-accent-dim text-accent border border-accent/20"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-hover"
                }`}
            >
              <Bot className="w-4 h-4" />
              Ask AI
            </button>
            <button
              onClick={reload}
              title="Refresh data"
              className="btn-ghost p-2"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={reset}
              title="Upload new portfolio"
              className="btn-ghost p-2 text-text-muted hover:text-loss"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-5 py-6 space-y-6">
        {/* Summary stats */}
        {summary && <SummaryCards summary={summary} />}

        {/* Trend + insights + optional chat */}
        <div className={`grid gap-6 ${showChat ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1"}`}>
          <div className="space-y-6">
            <PortfolioValueChart history={history} />
            {summary && <SectorChart sectors={summary.sectors} />}
            <InsightsPanel insights={insights} />
          </div>
          {showChat && <ChatPanel />}
        </div>

        {/* Holdings table */}
        <HoldingsTable holdings={holdings} />
      </main>
    </div>
  )
}
