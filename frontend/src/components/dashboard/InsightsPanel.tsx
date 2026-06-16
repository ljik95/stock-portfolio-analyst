import { AlertTriangle, Info, Sparkles, Lightbulb } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Insight } from "@/lib/api"

interface InsightsPanelProps {
  insights: Insight[]
}

const SEVERITY_STYLES: Record<Insight["severity"], { icon: typeof AlertTriangle; iconClass: string; badgeClass: string }> = {
  warning: {
    icon: AlertTriangle,
    iconClass: "text-loss",
    badgeClass: "bg-lossDim text-loss",
  },
  positive: {
    icon: Sparkles,
    iconClass: "text-accent",
    badgeClass: "bg-accent-dim text-accent",
  },
  info: {
    icon: Info,
    iconClass: "text-text-secondary",
    badgeClass: "bg-surface border border-surface-border text-text-secondary",
  },
}

export function InsightsPanel({ insights }: InsightsPanelProps) {
  if (!insights.length) return null

  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb className="w-3.5 h-3.5 text-text-muted" />
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">Insights</h3>
      </div>

      <div className="space-y-3">
        {insights.map((insight, i) => {
          const style = SEVERITY_STYLES[insight.severity] ?? SEVERITY_STYLES.info
          const Icon = style.icon
          return (
            <div key={i} className="flex gap-3">
              <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center shrink-0", style.badgeClass)}>
                <Icon className="w-3.5 h-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary">{insight.title}</p>
                <p className="text-xs text-text-secondary mt-0.5 leading-relaxed">{insight.detail}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
