import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Circle,
  Clock,
  Database,
  ExternalLink,
  FileText,
  Layers,
  Loader2,
  Radio,
  RefreshCw,
  Server,
  Sparkles,
  XCircle,
  Zap,
  AlertTriangle,
} from 'lucide-react'
import { api } from '../api'
import { Card, StatCard, StatusBadge, usePoll } from '../components/ui'
import {
  extractDisplayFields,
  extractUrlsFromText,
  formatIso,
  formatTimestamp,
  jobFailureMessage,
  pipelineStepStatus,
  resolveJobStatus,
  summarizeRequirement,
  type DisplayField,
} from '../lib/jobDisplay'

type PipelineStep = { name: string; via: string; status: string; error?: string }
type ScrapeEvent = {
  event_id?: string
  url?: string
  event_type?: string
  timestamp?: number
  processed_at?: number
  content_preview?: string
  processing_strategy?: string
  confidence?: number
  vertical?: string
  predictions?: Record<string, string>
  payload?: Record<string, unknown>
}

function StepIcon({ status }: { status: string }) {
  if (status === 'done') return <CheckCircle2 className="h-5 w-5 text-emerald-400" />
  if (status === 'failed') return <XCircle className="h-5 w-5 text-red-400" />
  if (status === 'active') return <Loader2 className="h-5 w-5 animate-spin text-accent-cyan" />
  return <Circle className="h-5 w-5 text-white/25" />
}

const STEP_ICONS = [FileText, Zap, Radio, Server, Database]

function ExpandableText({
  text,
  previewChars = 220,
}: {
  text: string
  previewChars?: number
}) {
  const [expanded, setExpanded] = useState(false)
  const isLong = text.length > previewChars

  return (
    <div>
      <p
        className={`whitespace-pre-wrap break-words text-base leading-relaxed text-white/90 ${
          !expanded && isLong ? 'line-clamp-4' : ''
        }`}
      >
        {text}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded(v => !v)}
          className="mt-3 text-xs font-medium text-accent-cyan transition hover:text-accent-cyan/80"
        >
          {expanded ? 'Show less' : 'Show full text'}
        </button>
      )}
    </div>
  )
}

function MetaChip({
  label,
  value,
  mono,
  accent,
}: {
  label?: string
  value: string
  mono?: boolean
  accent?: 'cyan' | 'violet'
}) {
  const accentCls =
    accent === 'violet'
      ? 'bg-accent-violet/10 text-accent-violet ring-accent-violet/20'
      : accent === 'cyan'
        ? 'bg-accent-cyan/10 text-accent-cyan ring-accent-cyan/20'
        : 'bg-white/5 text-white/80 ring-white/10'

  return (
    <span className={`inline-flex max-w-full items-center gap-1.5 rounded-full px-3 py-1.5 text-xs ring-1 ${accentCls}`}>
      {label && <span className="shrink-0 text-white/45">{label}</span>}
      <span className={`truncate ${mono ? 'font-mono' : ''}`} title={value}>
        {value}
      </span>
    </span>
  )
}

function FieldGrid({ fields, columns = 2 }: { fields: DisplayField[]; columns?: 2 | 3 }) {
  if (!fields.length) {
    return <p className="text-sm text-white/40">No additional fields</p>
  }
  const grid = columns === 3 ? 'sm:grid-cols-2 lg:grid-cols-3' : 'sm:grid-cols-2'
  return (
    <dl className={`grid grid-cols-1 gap-3 ${grid}`}>
      {fields.map(f => (
        <div key={`${f.label}-${f.value.slice(0, 24)}`} className="rounded-xl bg-white/[0.03] px-4 py-3 ring-1 ring-white/5">
          <dt className="text-[11px] font-medium uppercase tracking-wide text-white/40">{f.label}</dt>
          <dd className={`mt-1 break-all text-sm text-white/85 ${f.mono ? 'font-mono text-accent-cyan' : ''}`}>
            {f.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export default function ScrapeJobDetail() {
  const { jobId = '' } = useParams()
  const { data: job, loading: jobLoading } = usePoll(
    () => (jobId ? api.scrapeJob(jobId) : Promise.reject(new Error('no job'))),
    5000,
  )
  const { data: results, loading: eventsLoading, refresh } = usePoll(
    () => (jobId ? api.scrapeJobEvents(jobId, 20) : Promise.resolve({ events: [], total: 0, pipeline: [] })),
    5000,
  )

  const config = (job?.config && typeof job.config === 'object' ? job.config : {}) as Record<string, unknown>
  const pipeline = (results?.pipeline as PipelineStep[]) || []
  const events = (results?.events as ScrapeEvent[]) || []
  const urls = Array.isArray(config.urls) ? config.urls : config.url ? [config.url] : []
  const requirementUrls = extractUrlsFromText(job?.requirement)
  const allUrls = [...new Set([...urls.map(String), ...requirementUrls])]
  const pageTitle = summarizeRequirement(job?.requirement, 120)
  const resolved = resolveJobStatus(job || {})
  const failureMsg = jobFailureMessage(job || {})

  const jobFields = extractDisplayFields({
    job_id: job?.job_id,
    tenant_name: job?.tenant_name,
    tenant_id: job?.tenant_id,
    plan: job?.plan,
    status: job?.status,
    pages_crawled: job?.pages_crawled,
    progress_pct: job?.progress_pct ? `${job.progress_pct}%` : undefined,
    created_at: formatIso(job?.created_at),
    updated_at: formatIso(job?.updated_at),
    error_message: job?.error_message,
  })

  const planFields = extractDisplayFields({
    type: config.type,
    vertical: config.vertical,
    max_pages: config.max_pages,
    max_depth: config.max_depth,
    event_type: config.event_type,
  })

  if (jobLoading && !job) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent-cyan" />
      </div>
    )
  }

  if (!job && !jobLoading) {
    return (
      <div>
        <Link to="/ingestion" className="mb-6 inline-flex items-center gap-2 text-sm text-accent-cyan hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back to Ingestion
        </Link>
        <Card>
          <p className="text-white/60">Job not found: <span className="font-mono text-accent-cyan">{jobId}</span></p>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <Link
        to="/ingestion"
        className="mb-6 inline-flex items-center gap-2 text-sm text-white/50 transition hover:text-accent-cyan"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Ingestion
      </Link>

      <header className="mb-8">
        <p className="text-xs font-medium uppercase tracking-wider text-accent-violet">Job results</p>

        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold leading-snug tracking-tight text-white sm:text-3xl">
              {pageTitle}
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-white/45">
              Live pipeline output for this scrape — from user request through Kafka to processed records.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              {job?.tenant_name && <MetaChip label="Tenant" value={job.tenant_name} />}
              {job?.plan && <MetaChip value={String(job.plan)} accent="violet" />}
              <MetaChip label="Job" value={String(job?.job_id || jobId)} mono accent="cyan" />
              {job?.created_at && <MetaChip label="Started" value={formatIso(job.created_at)} />}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3 self-start">
            <StatusBadge status={resolved.badge} />
            <span className={`rounded-full px-3 py-1.5 text-sm capitalize ring-1 ring-white/10 ${
              resolved.failed ? 'bg-red-500/10 text-red-300' : 'bg-white/5 text-white/70'
            }`}>
              {resolved.status}
            </span>
          </div>
        </div>

        {failureMsg && (
          <div className="mt-4 flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-4 ring-1 ring-red-500/20">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
            <div>
              <p className="text-sm font-semibold text-red-200">Job did not collect data</p>
              <p className="mt-1 text-sm leading-relaxed text-red-200/80">{failureMsg}</p>
            </div>
          </div>
        )}

        {job?.requirement && (
          <Card className="mt-6 border-accent-cyan/10 bg-gradient-to-br from-accent-cyan/[0.06] to-accent-violet/[0.04] !p-5 sm:!p-6">
            <p className="text-xs font-medium uppercase tracking-wide text-white/40">What the user asked for</p>
            <div className="mt-3">
              <ExpandableText text={String(job.requirement)} />
            </div>
            {allUrls.length > 0 && (
              <div className="mt-5 border-t border-white/10 pt-4">
                <p className="mb-2 text-xs font-medium uppercase text-white/40">Targets mentioned</p>
                <div className="flex flex-col gap-2">
                  {allUrls.map(url => (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-start gap-2 rounded-xl bg-black/20 px-3 py-2.5 text-sm text-accent-cyan ring-1 ring-white/5 transition hover:bg-black/30"
                    >
                      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span className="break-all font-mono text-xs leading-relaxed sm:text-sm">{url}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}
      </header>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Progress" value={`${job?.progress_pct ?? 0}%`} accent="cyan" />
        <StatCard label="Pages crawled" value={job?.pages_crawled ?? 0} accent="violet" />
        <StatCard label="Processed events" value={results?.total ?? 0} accent="emerald" />
        <StatCard label="Data source" value={results?.source || '—'} accent="cyan" />
      </div>

      {/* Pipeline journey — investor-friendly */}
      <Card className="mb-8">
        <div className="mb-6 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">End-to-end pipeline</h3>
            <p className="mt-1 text-sm text-white/45">
              Live path from user request → crawl → Kafka → stream processing → stored results
            </p>
          </div>
          <button
            type="button"
            onClick={() => refresh()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-white/5 px-3 py-2 text-xs text-accent-cyan ring-1 ring-white/10 transition hover:bg-white/10"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${eventsLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="space-y-3">
          {pipeline.map((step, i) => {
            const Icon = STEP_ICONS[i] || Circle
            const st = step.status
            return (
              <div
                key={step.name}
                className={`flex items-start gap-4 rounded-xl border px-4 py-4 transition ${
                  st === 'done'
                    ? 'border-emerald-500/20 bg-emerald-500/[0.05]'
                    : st === 'failed'
                      ? 'border-red-500/20 bg-red-500/[0.05]'
                      : st === 'active'
                        ? 'border-accent-cyan/25 bg-accent-cyan/[0.05]'
                        : 'border-white/10 bg-white/[0.02]'
                }`}
              >
                <div className="mt-0.5 flex flex-col items-center gap-2">
                  <div className="rounded-lg bg-white/5 p-2 ring-1 ring-white/10">
                    <Icon className="h-4 w-4 text-accent-cyan" />
                  </div>
                  {i < pipeline.length - 1 && <div className="hidden h-6 w-px bg-white/10 sm:block" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-white/90">
                      <span className="mr-2 text-white/35">{i + 1}.</span>
                      {step.name}
                    </p>
                    <div className="flex items-center gap-2">
                      <StepIcon status={st} />
                      <StatusBadge status={pipelineStepStatus(st)} />
                    </div>
                  </div>
                    <p className="mt-1 text-xs text-white/45">{step.via}</p>
                    {step.error && (
                      <p className="mt-2 text-xs leading-relaxed text-red-300/90">{step.error}</p>
                    )}
                  </div>
              </div>
            )
          })}
          {!pipeline.length && (
            <p className="text-sm text-white/40">{eventsLoading ? 'Loading pipeline status…' : 'Pipeline status unavailable'}</p>
          )}
        </div>

        {events.length > 0 && (
          <div className="mt-6 flex items-center gap-3 rounded-xl bg-emerald-500/10 px-4 py-3.5 ring-1 ring-emerald-500/25">
            <Sparkles className="h-5 w-5 shrink-0 text-emerald-400" />
            <p className="text-sm text-emerald-200/90">
              Data successfully flowed through the full pipeline — {events.length} processed record{events.length !== 1 ? 's' : ''} ready for apps & analytics.
            </p>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Job request */}
        <Card>
          <h3 className="mb-4 text-lg font-semibold">Job details</h3>
          <FieldGrid fields={jobFields} />
        </Card>

        {/* Crawl plan */}
        <Card>
          <h3 className="mb-4 text-lg font-semibold">Crawl plan</h3>
          {allUrls.length > 0 && (
            <div className="mb-5 space-y-2">
              <p className="text-xs font-medium uppercase text-white/40">Target URLs</p>
              {allUrls.map(u => (
                <a
                  key={u}
                  href={u}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-start gap-2 rounded-xl bg-white/[0.03] px-4 py-3 text-sm text-accent-cyan ring-1 ring-white/5 transition hover:bg-white/[0.06]"
                >
                  <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span className="break-all font-mono text-xs leading-relaxed">{u}</span>
                </a>
              ))}
            </div>
          )}
          <FieldGrid fields={planFields} />
          {!allUrls.length && !planFields.length && (
            <p className="text-sm text-white/40">Plan details will appear once the orchestrator assigns targets.</p>
          )}
        </Card>
      </div>

      {/* Processed data */}
      <Card className="mt-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">Processed data</h3>
            <p className="mt-1 text-sm text-white/45">
              Last {events.length} events from <span className="font-mono text-accent-cyan">processed_stream</span>
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 text-xs text-white/50">
            <Clock className="h-3.5 w-3.5" /> Auto-refreshes every 5s
          </span>
        </div>

        {eventsLoading && !events.length && (
          <div className="flex items-center gap-3 py-12 text-white/40">
            <Loader2 className="h-5 w-5 animate-spin text-accent-cyan" />
            Loading processed events…
          </div>
        )}

        {!eventsLoading && !events.length && (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 py-12 text-center">
            <Layers className="mx-auto h-10 w-10 text-white/20" />
            <p className="mt-4 text-sm text-white/55">No processed events yet for this job.</p>
            <p className="mx-auto mt-2 max-w-md text-xs text-white/35">
              Events appear after the worker crawls pages, publishes to raw_stream, and the stream processor writes to processed_stream.
            </p>
            {job?.status === 'running' && (
              <p className="mt-4 inline-flex items-center gap-2 text-xs text-accent-cyan">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Job still running — check back shortly
              </p>
            )}
          </div>
        )}

        <div className="space-y-5">
          {events.map((ev, idx) => {
            const original = (ev.payload?.original as Record<string, unknown>) || {}
            const metaFields = extractDisplayFields({
              event_id: ev.event_id,
              event_type: ev.event_type,
              vertical: ev.vertical,
              url: ev.url,
              processing_strategy: ev.processing_strategy,
              confidence: ev.confidence,
              timestamp: formatTimestamp(ev.timestamp),
              processed_at: formatTimestamp(ev.processed_at),
              ...(ev.predictions || {}),
            })
            const dataFields = extractDisplayFields(original)
            const preview = ev.content_preview && !ev.content_preview.startsWith('{')
              ? ev.content_preview
              : dataFields.find(f => f.label === 'Title' || f.label === 'Text')?.value

            return (
              <div
                key={ev.event_id || idx}
                className="overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.04] to-transparent"
              >
                <div className="border-b border-white/10 px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-medium uppercase tracking-wide text-accent-violet">
                        Record {idx + 1}
                      </p>
                      <h4 className="mt-1 break-all font-mono text-sm text-accent-cyan">
                        {ev.url || ev.event_type || 'Processed event'}
                      </h4>
                      {preview && preview !== '—' && (
                        <p className="mt-2 line-clamp-3 whitespace-pre-wrap break-words text-sm leading-relaxed text-white/70">
                          {preview}
                        </p>
                      )}
                    </div>
                    {ev.url && (
                      <a
                        href={ev.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-accent-cyan/10 px-3 py-1.5 text-xs text-accent-cyan ring-1 ring-accent-cyan/25"
                      >
                        Open source <ArrowRight className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                </div>

                <div className="grid gap-6 p-5 lg:grid-cols-2">
                  <div>
                    <p className="mb-3 text-xs font-medium uppercase text-white/40">Event metadata</p>
                    <FieldGrid fields={metaFields} columns={2} />
                  </div>
                  <div>
                    <p className="mb-3 text-xs font-medium uppercase text-white/40">Extracted data</p>
                    <FieldGrid fields={dataFields.length ? dataFields : [{ label: 'Preview', value: ev.content_preview || '—' }]} columns={2} />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <div className="mt-8 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.02] px-5 py-4 text-sm text-white/50">
        <Sparkles className="h-4 w-4 shrink-0 text-accent-violet" />
        <span>
          This page shows live platform data — ideal for MVP demos and investor walkthroughs.
          Run a new scrape from <Link to="/tenants" className="text-accent-cyan hover:underline">Tenants</Link>.
        </span>
      </div>
    </div>
  )
}
