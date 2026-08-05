import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  Rocket,
  ShieldCheck,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { api } from '../api'
import { Card, PageHeader, ProgressBar, StatCard, usePoll } from '../components/ui'

type DemoStep = { key: string; label: string; status: 'queued' | 'running' | 'passed' | 'failed'; detail?: string; ms?: number }
type DemoResult = { ok: boolean; steps: DemoStep[] }

const EXPECTED: DemoStep[] = [
  { key: 'tenant', label: 'Provision starter tenant', status: 'queued' },
  { key: 'scrape', label: 'Submit AI-planned scrape job', status: 'queued' },
  { key: 'pipeline', label: 'Crawl → raw_stream → processed_stream', status: 'queued' },
  { key: 'brain', label: 'Brain verifies pipeline objective', status: 'queued' },
]

function StepIcon({ status }: { status: DemoStep['status'] }) {
  if (status === 'passed') return <CheckCircle2 className="h-5 w-5 text-emerald-400" />
  if (status === 'failed') return <XCircle className="h-5 w-5 text-red-400" />
  if (status === 'running') return <Loader2 className="h-5 w-5 animate-spin text-accent-cyan" />
  return <Circle className="h-5 w-5 text-white/25" />
}

export default function Showcase() {
  const { data: status } = usePoll(() => api.mvpStatus(), 5000)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<DemoResult | null>(null)
  const [activeIdx, setActiveIdx] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const timers = useRef<number[]>([])

  useEffect(() => () => timers.current.forEach(clearInterval), [])

  const runDemo = async () => {
    setRunning(true)
    setResult(null)
    setActiveIdx(0)
    setElapsed(0)
    const started = Date.now()
    const tick = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250)
    const advance = window.setInterval(() => setActiveIdx(i => Math.min(i + 1, EXPECTED.length - 1)), 4000)
    timers.current = [tick, advance]
    try {
      const res = await api.mvpDemo({})
      setResult(res)
    } catch (e) {
      setResult({ ok: false, steps: [{ key: 'error', label: 'Demo request failed', status: 'failed', detail: String(e) }] })
    } finally {
      timers.current.forEach(clearInterval)
      setRunning(false)
    }
  }

  // While running, synthesize a live-looking step list from EXPECTED + activeIdx.
  const displaySteps: DemoStep[] = result
    ? result.steps
    : running
      ? EXPECTED.map((s, i) => ({ ...s, status: i < activeIdx ? 'running' : i === activeIdx ? 'running' : 'queued' }))
      : EXPECTED

  const readyPct = status ? Math.round((status.capabilities_ready / status.capabilities_total) * 100) : 0

  return (
    <div>
      <PageHeader
        title="MVP Showcase"
        subtitle="Proof the platform works — live service health, delivered capabilities, and a one-click end-to-end demo"
      />

      {/* Scorecard */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Services Online" value={status ? `${status.services_up}/${status.services_total}` : '—'} accent="emerald" />
        <StatCard label="Capabilities Ready" value={status ? `${status.capabilities_ready}/${status.capabilities_total}` : '—'} accent="cyan" />
        <StatCard label="Brain Objectives" value={status ? status.metrics.brain_objectives : '—'} accent="violet" />
        <StatCard label="Jobs Completed" value={status ? status.metrics.completed_jobs : '—'} accent="emerald" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Capabilities checklist */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold">MVP Capabilities</h3>
            <span className="text-sm text-white/50">{readyPct}% ready</span>
          </div>
          <ProgressBar value={readyPct} />
          <div className="mt-5 space-y-2.5">
            {status?.capabilities?.map((c: any) => (
              <div key={c.key} className="flex items-start gap-3 rounded-xl bg-white/[0.03] px-3.5 py-3">
                {c.ready ? (
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
                ) : (
                  <Clock className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
                )}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white/85">{c.title}</p>
                  <p className="text-xs text-white/40">{c.layer}</p>
                </div>
              </div>
            ))}
            {!status && <p className="text-white/40">Loading capabilities…</p>}
          </div>
        </Card>

        {/* Live demo runner */}
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">Live End-to-End Demo</h3>
            {(running || result) && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-2.5 py-1 text-xs text-white/60">
                <Clock className="h-3.5 w-3.5" /> {elapsed}s
              </span>
            )}
          </div>

          <p className="mb-5 text-sm text-white/55">
            Runs the real pipeline: provision a tenant → submit an AI-planned scrape → stream it through Kafka → let the
            Brain plan, execute and verify every step.
          </p>

          <button
            type="button"
            onClick={runDemo}
            disabled={running}
            className="btn-action-primary flex w-full items-center justify-center gap-2 px-5 disabled:cursor-not-allowed"
          >
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
            {running ? 'Running live demo…' : result ? 'Run demo again' : 'Run live end-to-end demo'}
          </button>

          <div className="mt-6 space-y-2.5">
            {displaySteps.map((s, i) => (
              <div
                key={s.key + i}
                className={`flex items-start gap-3 rounded-xl border px-3.5 py-3 transition ${
                  s.status === 'passed'
                    ? 'border-emerald-500/20 bg-emerald-500/[0.06]'
                    : s.status === 'failed'
                      ? 'border-red-500/20 bg-red-500/[0.06]'
                      : s.status === 'running'
                        ? 'border-accent-cyan/25 bg-accent-cyan/[0.06]'
                        : 'border-white/10 bg-white/[0.02]'
                }`}
              >
                <div className="mt-0.5">
                  <StepIcon status={s.status} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white/85">
                      <span className="mr-2 text-white/35">{i + 1}.</span>
                      {s.label}
                    </p>
                    {typeof s.ms === 'number' && s.ms > 0 && <span className="shrink-0 text-xs text-white/35">{s.ms} ms</span>}
                  </div>
                  {s.detail && <p className="mt-1 text-xs text-white/50">{s.detail}</p>}
                </div>
              </div>
            ))}
          </div>

          {result && (
            <div
              className={`mt-5 flex items-center gap-3 rounded-xl px-4 py-3.5 ${
                result.ok
                  ? 'bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30'
                  : 'bg-red-500/10 text-red-300 ring-1 ring-red-500/30'
              }`}
            >
              {result.ok ? <ShieldCheck className="h-5 w-5 shrink-0" /> : <XCircle className="h-5 w-5 shrink-0" />}
              <p className="text-sm font-medium">
                {result.ok
                  ? 'MVP verified end-to-end — tenant, scrape, Kafka pipeline and Brain all green.'
                  : 'Demo did not fully pass — inspect the failing step above and service logs.'}
              </p>
            </div>
          )}
        </Card>
      </div>

      {/* Footnote */}
      <div className="mt-8 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.02] px-5 py-4 text-sm text-white/50">
        <Sparkles className="h-4 w-4 shrink-0 text-accent-violet" />
        <span>
          Everything on this page is powered by live platform services — no mocks. Open the{' '}
          <a href="/overview" className="text-accent-cyan hover:underline">Overview</a> and{' '}
          <a href="/brain" className="text-accent-cyan hover:underline">Brain</a> pages to explore further.
        </span>
      </div>

      <div className="mt-4 flex items-center gap-2 text-xs text-white/30">
        <Activity className="h-3.5 w-3.5" /> Scorecard refreshes every 5s
      </div>
    </div>
  )
}
