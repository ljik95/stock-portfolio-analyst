"use client"

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts"
import { chartColor } from "@/lib/utils"

interface SectorChartProps {
  sectors: Record<string, number>
}

export function SectorChart({ sectors }: SectorChartProps) {
  const data = Object.entries(sectors)
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({ name, value }))

  if (!data.length) return null

  return (
    <div className="card p-5">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-4">Sector Allocation</h3>

      <div className="flex gap-6 items-center">
        <div className="w-36 h-36 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={38}
                outerRadius={60}
                paddingAngle={2}
                dataKey="value"
                strokeWidth={0}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={chartColor(i)} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#13161e",
                  border: "1px solid #1e2330",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "#e8eaf0",
                }}
                formatter={(value: number) => [`${value.toFixed(1)}%`, ""]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col gap-2 flex-1 min-w-0">
          {data.map((entry, i) => (
            <div key={entry.name} className="flex items-center gap-2 text-sm">
              <div
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: chartColor(i) }}
              />
              <span className="text-text-secondary truncate flex-1">{entry.name}</span>
              <span className="font-mono text-xs text-text-primary tabular-nums">
                {entry.value.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
