"use client"

import { useCallback, useState } from "react"
import { useDropzone } from "react-dropzone"
import { Upload, FileText, ExternalLink, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface UploadZoneProps {
  onUpload: (file: File) => void
  loading: boolean
  error: string | null
}

export function UploadZone({ onUpload, loading, error }: UploadZoneProps) {
  const [dragActive, setDragActive] = useState(false)

  const onDrop = useCallback(
    (accepted: File[]) => { if (accepted[0]) onUpload(accepted[0]) },
    [onUpload]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4">
      {/* Logo */}
      <div className="mb-10 text-center">
        <div className="flex items-center justify-center gap-2 mb-3">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <span className="text-surface font-bold text-sm">PA</span>
          </div>
          <span className="text-xl font-semibold text-text-primary">Portfolio Analyst</span>
        </div>
        <p className="text-text-secondary text-sm">AI-powered insights for your Robinhood portfolio</p>
      </div>

      {/* Dropzone card */}
      <div
        {...getRootProps()}
        className={cn(
          "card w-full max-w-lg p-10 text-center cursor-pointer transition-all duration-200",
          "hover:border-accent/40 hover:shadow-glow",
          isDragActive && "border-accent shadow-glow bg-accent-dim",
          loading && "opacity-60 cursor-not-allowed"
        )}
      >
        <input {...getInputProps()} />

        <div className={cn(
          "w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5 transition-colors",
          isDragActive ? "bg-accent text-surface" : "bg-surface border border-surface-border text-accent"
        )}>
          {loading
            ? <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            : <Upload className="w-6 h-6" />
          }
        </div>

        <h2 className="text-lg font-semibold mb-2">
          {loading ? "Importing your portfolio…" : "Drop your Robinhood CSV here"}
        </h2>
        <p className="text-text-secondary text-sm mb-1">or click to browse files</p>
        <p className="text-text-muted text-xs">Accepts .csv files up to 5 MB</p>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 flex items-start gap-2 text-loss text-sm max-w-lg w-full bg-lossDim border border-loss/20 rounded-lg px-4 py-3">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* How to export instructions */}
      <div className="mt-8 max-w-lg w-full card p-5">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-3">How to export from Robinhood</p>
        <ol className="space-y-2">
          {[
            "Open Robinhood → tap your account icon",
            "Go to Statements & History",
            'Tap "Export to CSV" and save the file',
            "Drag and drop the file above",
          ].map((step, i) => (
            <li key={i} className="flex gap-3 text-sm text-text-secondary">
              <span className="font-mono text-accent text-xs mt-0.5 shrink-0">
                {String(i + 1).padStart(2, "0")}
              </span>
              {step}
            </li>
          ))}
        </ol>
        <a
          href="https://robinhood.com/account/history"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          <ExternalLink className="w-3 h-3" />
          Open Robinhood account history
        </a>
      </div>
    </div>
  )
}
