const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// ─── Token management (localStorage) ────────────────────────────────────────

const TOKEN_KEY = "portfolio_token"

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// ─── Base fetch ───────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> ?? {}),
  }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}/api/v1${path}`, { ...options, headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? "Unknown error")
  }
  return res.json()
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Holding {
  id: string
  ticker: string
  name: string | null
  quantity: number
  average_cost: number | null
  current_price: number | null
  current_value: number | null
  total_return: number | null
  return_pct: number | null
  sector: string | null
  asset_type: string
}

export interface PortfolioSummary {
  total_value: number
  total_cost: number
  total_return: number
  total_return_pct: number
  num_holdings: number
  top_holding: string | null
  sectors: Record<string, number>
}

export interface PortfolioResponse {
  portfolio: { id: string; name: string; broker: string; imported_at: string }
  summary: PortfolioSummary
}

export interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  created_at: string
}

export interface ChatResponse {
  conversation_id: string
  message: Message
}

export interface PricePoint {
  date: string
  close: number
  volume?: number
}

// ─── API methods ──────────────────────────────────────────────────────────────

export const api = {
  async importPortfolio(file: File, name?: string): Promise<{ token: string; portfolio_id: string; name: string }> {
    const form = new FormData()
    form.append("file", file)
    if (name) form.append("name", name)

    const token = getToken()
    const headers: Record<string, string> = {}
    if (token) headers["Authorization"] = `Bearer ${token}`

    const res = await fetch(`${API_BASE}/api/v1/portfolio/import`, {
      method: "POST",
      headers,
      body: form,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(res.status, body.detail)
    }
    return res.json()
  },

  getPortfolio: () =>
    apiFetch<PortfolioResponse>("/portfolio/me"),

  getHoldings: () =>
    apiFetch<Holding[]>("/portfolio/me/holdings"),

  getPriceHistory: (ticker: string, days = 90) =>
    apiFetch<{ ticker: string; prices: PricePoint[] }>(`/portfolio/me/history/${ticker}?days=${days}`),

  sendMessage: (message: string, conversation_id?: string) =>
    apiFetch<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id }),
    }),

  health: () =>
    fetch(`${API_BASE}/health`).then(r => r.json()),
}
