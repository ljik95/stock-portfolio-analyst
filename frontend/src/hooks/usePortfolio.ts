"use client"

import { useState, useEffect, useCallback } from "react"
import { api, getToken, setToken, clearToken, type Holding, type PortfolioSummary, type ApiError } from "@/lib/api"

export type AppState = "idle" | "loading" | "ready" | "error"

export function usePortfolio() {
  const [state,    setState]    = useState<AppState>("idle")
  const [summary,  setSummary]  = useState<PortfolioSummary | null>(null)
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [error,    setError]    = useState<string | null>(null)

  const loadPortfolio = useCallback(async () => {
    if (!getToken()) { setState("idle"); return }
    setState("loading")
    setError(null)
    try {
      const [portfolioRes, holdingsRes] = await Promise.all([
        api.getPortfolio(),
        api.getHoldings(),
      ])
      setSummary(portfolioRes.summary)
      setHoldings(holdingsRes)
      setState("ready")
    } catch (err: any) {
      if (err?.status === 401) {
        clearToken()
        setState("idle")
      } else {
        setError(err.message ?? "Failed to load portfolio")
        setState("error")
      }
    }
  }, [])

  // Auto-load on mount if token exists
  useEffect(() => { loadPortfolio() }, [loadPortfolio])

  const importCSV = useCallback(async (file: File) => {
    setState("loading")
    setError(null)
    try {
      const { token } = await api.importPortfolio(file)
      setToken(token)
      await loadPortfolio()
    } catch (err: any) {
      setError(err.message ?? "Failed to import portfolio")
      setState("error")
    }
  }, [loadPortfolio])

  const reset = useCallback(() => {
    clearToken()
    setSummary(null)
    setHoldings([])
    setState("idle")
  }, [])

  return { state, summary, holdings, error, importCSV, reload: loadPortfolio, reset }
}
