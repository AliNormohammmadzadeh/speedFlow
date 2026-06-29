import { useEffect, useState } from 'react'
import { ExternalLink, FileText, HeartPulse, X } from 'lucide-react'
import { api } from '../api'
import { useDetail } from '../context/DetailContext'
import { StatusBadge } from './ui'

type Tab = 'info' | 'health' | 'logs'

export default function DetailDrawer() {
  const { detail, closeDetail } = useDetail()
  const [tab, setTab] = useState<Tab>('info')
  const [logs, setLogs] = useState<string[]>([])
  const [logsLoading, setLogsLoading] = useState(false)

  useEffect(() => {
    if (!detail) return
    setTab('info')
    setLogs([])
  }, [detail])

  useEffect(() => {
    const logKey = detail?.logName || (detail?.data?.container as string | undefined)
    if (!logKey || tab !== 'logs') return
    setLogsLoading(true)
    const useDocker = !detail.logName && !!detail.data?.container
    api.logs(logKey, 80, useDocker ? String(detail.data?.container) : undefined)
      .then(r => setLogs(r.lines || []))
      .catch(() => setLogs(['Failed to load logs']))
      .finally(() => setLogsLoading(false))
  }, [detail?.logName, detail?.data?.container, tab])

  if (!detail) return null

  const health = detail.data?.health as Record<string, unknown> | undefined
  const status = (health?.status as string) || (detail.data?.status as string) || undefined

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm animate-fade-in"
        onClick={closeDetail}
        aria-hidden
      />
      <aside
        className="detail-drawer fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l border-white/10 bg-[#0a0a12]/95 shadow-2xl backdrop-blur-2xl animate-slide-in-right"
        role="dialog"
        aria-label={detail.title}
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-5">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wider text-accent-cyan">{detail.kind}</p>
            <h2 className="mt-1 truncate text-xl font-bold">{detail.title}</h2>
            {detail.subtitle && <p className="mt-1 text-sm text-white/50">{detail.subtitle}</p>}
            {status && (
              <div className="mt-3">
                <StatusBadge status={status} />
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={closeDetail}
            className="btn-icon shrink-0"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="flex gap-1 border-b border-white/10 px-4">
          {([
            ['info', 'Info', FileText],
            ['health', 'Health', HeartPulse],
            ...(detail.logName || detail.data?.container ? [['logs', 'Logs', FileText] as const] : []),
          ] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id as Tab)}
              className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${
                tab === id
                  ? 'border-accent-cyan text-accent-cyan'
                  : 'border-transparent text-white/50 hover:text-white'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {tab === 'info' && (
            <div className="space-y-4">
              {detail.data?.description && (
                <p className="text-sm leading-relaxed text-white/70">{String(detail.data.description)}</p>
              )}
              {detail.data?.layer && (
                <Row label="Layer" value={String(detail.data.layer)} />
              )}
              {detail.data?.port != null && (
                <Row label="Port" value={String(detail.data.port)} mono />
              )}
              {detail.data?.container && (
                <Row label="Container" value={String(detail.data.container)} mono />
              )}
              {detail.healthUrl && (
                <a
                  href={detail.healthUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-xl bg-accent-cyan/10 px-4 py-2 text-sm text-accent-cyan ring-1 ring-accent-cyan/30 transition hover:bg-accent-cyan/20"
                >
                  Open health endpoint
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              )}
              {detail.data && Object.keys(detail.data).length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase text-white/40">Raw data</p>
                  <pre className="max-h-80 overflow-auto rounded-xl bg-black/50 p-4 text-xs leading-relaxed text-white/70">
                    {JSON.stringify(detail.data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {tab === 'health' && (
            <div>
              {health ? (
                <pre className="overflow-auto rounded-xl bg-black/50 p-4 text-xs text-white/70">
                  {JSON.stringify(health, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-white/40">No live health probe data for this item.</p>
              )}
            </div>
          )}

          {tab === 'logs' && (detail.logName || detail.data?.container) && (
            <div>
              {logsLoading ? (
                <p className="text-sm text-white/40">Loading logs…</p>
              ) : (
                <pre className="max-h-[60vh] overflow-auto rounded-xl bg-black/60 p-4 font-mono text-[11px] leading-relaxed text-emerald-300/90">
                  {logs.length ? logs.join('\n') : '(empty log)'}
                </pre>
              )}
              <button
                type="button"
                className="mt-4 text-xs text-accent-cyan hover:underline"
                onClick={() => {
                  setLogsLoading(true)
                  const logKey = detail.logName || String(detail.data?.container)
                  const useDocker = !detail.logName && !!detail.data?.container
                  api.logs(logKey, 80, useDocker ? String(detail.data?.container) : undefined)
                    .then(r => setLogs(r.lines || []))
                    .finally(() => setLogsLoading(false))
                }}
              >
                Refresh logs
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-white/5 px-4 py-3">
      <span className="text-sm text-white/50">{label}</span>
      <span className={`text-sm ${mono ? 'font-mono text-accent-cyan' : 'text-white/80'}`}>{value}</span>
    </div>
  )
}
