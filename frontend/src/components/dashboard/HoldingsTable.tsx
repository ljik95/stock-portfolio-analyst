"use client"

import { useState } from "react"
import { ArrowUpDown, TrendingUp, TrendingDown } from "lucide-react"
import { formatCurrency, formatPct, formatNumber, formatDate, isPositive, shortName, cn } from "@/lib/utils"
import type { Holding } from "@/lib/api"

type SortKey = "purchased_at" | "ticker" | "current_value" | "return_pct" | "quantity"

interface HoldingsTableProps {
  holdings: Holding[]
  onSelectTicker?: (ticker: string) => void
}

/** Compare two values; nulls always sort last regardless of direction. */
function compareNullLast(av: string | number | null, bv: string | number | null, asc: boolean): number {
  if (av == null && bv == null) return 0
  if (av == null) return 1   // a is null → goes after b
  if (bv == null) return -1  // b is null → a goes before b
  if (asc) return av < bv ? -1 : av > bv ? 1 : 0
  return av > bv ? -1 : av < bv ? 1 : 0
}

export function HoldingsTable({ holdings, onSelectTicker }: HoldingsTableProps) {
  // Show the Purchased column only when at least one holding has a date.
  // Standard Robinhood Holdings exports don't include acquisition dates,
  // so this avoids an always-empty column full of dashes.
  const hasDates = holdings.some(h => h.purchased_at != null)

  // Default sort: chronological when dates exist; largest position first otherwise.
  const [sortKey, setSortKey] = useState<SortKey>(hasDates ? "purchased_at" : "current_value")
  const [sortAsc, setSortAsc] = useState(hasDates)

  const sorted = [...holdings].sort((a, b) => {
    const av = a[sortKey] as string | number | null
    const bv = b[sortKey] as string | number | null
    return compareNullLast(av, bv, sortAsc)
  })

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc(a => !a)
    // Date sorts ascending by default (oldest first); others descending
    else { setSortKey(key); setSortAsc(key === "purchased_at" || key === "ticker") }
  }

  const ColHeader = ({ label, k }: { label: string; k: SortKey }) => (
    <th
      className="text-left text-xs font-semibold uppercase tracking-wider text-text-muted pb-3 cursor-pointer select-none hover:text-text-secondary transition-colors"
      onClick={() => handleSort(k)}
    >
      <span className="flex items-center gap-1">
        {label}
        <ArrowUpDown className={cn("w-3 h-3", sortKey === k ? "text-accent" : "opacity-40")} />
      </span>
    </th>
  )

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-surface-border">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">Holdings</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="px-5">
              <th className="pl-5 text-left text-xs font-semibold uppercase tracking-wider text-text-muted pb-3 pt-4">Ticker</th>
              {hasDates && <ColHeader label="Purchased" k="purchased_at" />}
              <ColHeader label="Value"      k="current_value" />
              <ColHeader label="Qty"        k="quantity" />
              <ColHeader label="Return"     k="return_pct" />
              <th className="text-left text-xs font-semibold uppercase tracking-wider text-text-muted pb-3">Sector</th>
              <th className="pr-5 text-right text-xs font-semibold uppercase tracking-wider text-text-muted pb-3">Price</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {sorted.map((h) => {
              const pos = isPositive(h.return_pct)
              return (
                <tr
                  key={h.id}
                  className="hover:bg-surface-hover transition-colors cursor-pointer"
                  onClick={() => onSelectTicker?.(h.ticker)}
                >
                  <td className="pl-5 py-3.5">
                    <div className="flex flex-col">
                      <span className="font-mono font-semibold text-sm text-text-primary">{h.ticker}</span>
                      <span className="text-xs text-text-muted truncate max-w-[140px]">{shortName(h.name, h.ticker)}</span>
                    </div>
                  </td>
                  {hasDates && (
                    <td className="py-3.5 text-xs text-text-secondary font-mono whitespace-nowrap">
                      {formatDate(h.purchased_at)}
                    </td>
                  )}
                  <td className="py-3.5">
                    <span className="font-mono text-sm">{formatCurrency(h.current_value)}</span>
                  </td>
                  <td className="py-3.5 text-sm text-text-secondary font-mono">
                    {formatNumber(h.quantity, 4)}
                  </td>
                  <td className="py-3.5">
                    <div className="flex items-center gap-1.5">
                      {pos
                        ? <TrendingUp  className="w-3.5 h-3.5 text-accent" />
                        : <TrendingDown className="w-3.5 h-3.5 text-loss" />
                      }
                      <span className={cn("font-mono text-sm", pos ? "text-accent" : "text-loss")}>
                        {formatPct(h.return_pct)}
                      </span>
                    </div>
                    <div className="text-xs text-text-muted mt-0.5 font-mono">
                      {formatCurrency(h.total_return)}
                    </div>
                  </td>
                  <td className="py-3.5">
                    {h.sector
                      ? <span className="badge-sector">{h.sector}</span>
                      : <span className="text-text-muted text-xs">—</span>
                    }
                  </td>
                  <td className="pr-5 py-3.5 text-right font-mono text-sm text-text-secondary">
                    {formatCurrency(h.current_price)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
