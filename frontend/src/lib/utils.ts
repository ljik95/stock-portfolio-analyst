import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(value: number | null | undefined, compact = false): string {
  if (value == null) return "—"
  if (compact && Math.abs(value) >= 1_000_000)
    return `$${(value / 1_000_000).toFixed(2)}M`
  if (compact && Math.abs(value) >= 1_000)
    return `$${(value / 1_000).toFixed(1)}K`
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value)
}

export function formatPct(value: number | null | undefined): string {
  if (value == null) return "—"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "—"
  return value.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function isPositive(value: number | null | undefined): boolean {
  return value != null && value >= 0
}

/** Format an ISO date string (e.g. "2024-03-15") as "Mar 15, 2024". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—"
  const [y, m, d] = value.split("-").map(Number)
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

/** Truncate a ticker name for display. */
export function shortName(name: string | null, ticker: string): string {
  if (!name) return ticker
  return name.length > 24 ? name.slice(0, 22) + "…" : name
}

/** Returns a colour from a fixed palette based on index — for charts. */
const CHART_COLORS = [
  "#00d4aa", "#4f8ef7", "#f7c94f", "#f74f8e", "#9b59b6",
  "#e67e22", "#1abc9c", "#e74c3c", "#3498db", "#f39c12",
]

export function chartColor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length]
}
