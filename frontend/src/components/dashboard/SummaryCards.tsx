import { TrendingUp, TrendingDown, DollarSign, BarChart2 } from "lucide-react"
import { formatCurrency, formatPct, isPositive } from "@/lib/utils"
import type { PortfolioSummary } from "@/lib/api"
import { cn } from "@/lib/utils"

interface SummaryCardsProps {
  summary: PortfolioSummary
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const positive = isPositive(summary.total_return)
  const ReturnIcon = positive ? TrendingUp : TrendingDown

  const stats = [
    {
      label: "Portfolio Value",
      value: formatCurrency(summary.total_value),
      sub: `Cost basis ${formatCurrency(summary.total_cost, true)}`,
      icon: DollarSign,
      accent: false,
    },
    {
      label: "Total Return",
      value: formatCurrency(summary.total_return),
      sub: formatPct(summary.total_return_pct),
      icon: ReturnIcon,
      accent: true,
      positive,
    },
    {
      label: "Holdings",
      value: String(summary.num_holdings),
      sub: summary.top_holding ? `Largest: ${summary.top_holding}` : "positions",
      icon: BarChart2,
      accent: false,
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {stats.map((s) => (
        <div key={s.label} className="card p-5">
          <div className="flex items-start justify-between mb-3">
            <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">{s.label}</span>
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center",
              s.accent
                ? s.positive ? "bg-accent-dim text-accent" : "bg-lossDim text-loss"
                : "bg-surface border border-surface-border text-text-secondary"
            )}>
              <s.icon className="w-4 h-4" />
            </div>
          </div>
          <div className={cn(
            "stat-value mb-1",
            s.accent && (s.positive ? "text-accent" : "text-loss")
          )}>
            {s.value}
          </div>
          <div className="text-xs text-text-secondary">{s.sub}</div>
        </div>
      ))}
    </div>
  )
}
