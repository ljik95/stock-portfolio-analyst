"use client"

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts"
import { TrendingUp, TrendingDown } from "lucide-react"
import { formatCurrency, formatPct, isPositive, cn } from "@/lib/utils"
import type { ValuePoint } from "@/lib/api"

interface PortfolioValueChartProps {
  history: ValuePoint[]
}

export function PortfolioValueChart({ history }: PortfolioValueChartProps) {
  if (history.length < 2) return null

  const first = history[0].value
  const last  = history[history.length - 1].value
  const change    = last - first
  const changePct = first ? (change / first) * 100 : 0
  const positive  = isPositive(change)
  const Icon = positive ? TrendingUp : TrendingDown

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between mb-1">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">Portfolio Value</h3>
          <p className="text-xs text-text-muted mt-1">Last {history.length} days · assumes current holdings held throughout</p>
        </div>
        <div className={cn("flex items-center gap-1 text-sm font-mono", positive ? "text-accent" : "text-loss")}>
          <Icon className="w-3.5 h-3.5" />
          {formatPct(changePct)}
        </div>
      </div>

      <div className="h-48 mt-4 -ml-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="portfolioValueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={positive ? "#00d4aa" : "#ff4d6a"} stopOpacity={0.25} />
                <stop offset="100%" stopColor={positive ? "#00d4aa" : "#ff4d6a"} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2330" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: "#4a5568", fontSize: 11 }}
              tickFormatter={(d: string) => d.slice(5)}
              axisLine={{ stroke: "#1e2330" }}
              tickLine={false}
              minTickGap={32}
            />
            <YAxis
              tick={{ fill: "#4a5568", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => formatCurrency(v, true)}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                background: "#13161e",
                border: "1px solid #1e2330",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#e8eaf0",
              }}
              labelStyle={{ color: "#8892a4" }}
              formatter={(value) => [formatCurrency(value as number), "Value"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={positive ? "#00d4aa" : "#ff4d6a"}
              strokeWidth={2}
              fill="url(#portfolioValueGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
