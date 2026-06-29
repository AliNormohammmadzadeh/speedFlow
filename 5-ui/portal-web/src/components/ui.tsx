import React, { useEffect, useRef, useState } from 'react'
import { ChevronRight } from 'lucide-react'

export function usePoll<T>(fetcher: () => Promise<T>, ms = 5000) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    let active = true

    const load = async () => {
      try {
        const d = await fetcherRef.current()
        if (active) {
          setData(d)
          setError(null)
          setLoading(false)
        }
      } catch (e) {
        if (active) {
          setError(String(e))
          setLoading(false)
        }
      }
    }

    load()
    const id = setInterval(load, ms)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [ms])

  return {
    data,
    error,
    loading,
    refresh: () => fetcherRef.current().then(setData).catch(e => setError(String(e))),
  }
}

export function StatusBadge({ status }: { status: string }) {
  const cls = status === 'up' ? 'status-up' : status === 'degraded' ? 'status-degraded' : 'status-down'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${status === 'up' ? 'bg-emerald-400 animate-pulse' : status === 'degraded' ? 'bg-amber-400' : 'bg-red-400'}`} />
      {status}
    </span>
  )
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-8">
      <h2 className="text-3xl font-bold tracking-tight gradient-text">{title}</h2>
      {subtitle && <p className="mt-1 text-white/50">{subtitle}</p>}
    </header>
  )
}

export function Card({ children, className = '', onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`glass p-6 text-left ${onClick ? 'clickable-card' : ''} ${className}`}
    >
      {children}
    </Tag>
  )
}

export function ClickableRow({
  children,
  onClick,
  className = '',
}: {
  children: React.ReactNode
  onClick: () => void
  className?: string
}) {
  return (
    <button type="button" onClick={onClick} className={`clickable-row w-full ${className}`}>
      {children}
      <ChevronRight className="clickable-row-chevron h-4 w-4 shrink-0 text-white/20" />
    </button>
  )
}

export function StatCard({
  label,
  value,
  accent,
  onClick,
}: {
  label: string
  value: React.ReactNode
  accent?: 'cyan' | 'violet' | 'emerald'
  onClick?: () => void
}) {
  const accentCls = accent === 'cyan' ? 'text-accent-cyan' : accent === 'violet' ? 'text-accent-violet' : accent === 'emerald' ? 'text-emerald-400' : ''
  return (
    <Card onClick={onClick} className={onClick ? 'group' : ''}>
      <p className="text-sm text-white/50">{label}</p>
      <p className={`mt-2 text-4xl font-bold ${accentCls}`}>{value}</p>
      {onClick && (
        <p className="mt-3 text-xs text-white/30 opacity-0 transition group-hover:opacity-100">
          Click for details →
        </p>
      )}
    </Card>
  )
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-white/10">
      <div
        className="h-full rounded-full bg-gradient-to-r from-accent-cyan to-accent-violet transition-all duration-500"
        style={{ width: `${Math.min(100, value)}%` }}
      />
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-white/10 ${className}`} />
}
