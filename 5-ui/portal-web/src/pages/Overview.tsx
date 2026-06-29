import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import PipelineFlow from '../components/PipelineFlow'
import { Card, ClickableRow, PageHeader, Skeleton, StatCard, StatusBadge, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'
import { SERVICE_META } from '../lib/serviceMeta'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(SERVICE_META).map(([k, v]) => [k, v.label]),
)

export default function Overview() {
  const { data: overview, loading } = usePoll(() => api.overview())
  const { data: jobs } = usePoll(() => api.scrapeJobs())
  const { data: pipeline } = usePoll(() => api.pipeline())
  const { openDetail } = useDetail()
  const navigate = useNavigate()

  const chartData = jobs?.slice(0, 8).reverse().map(j => ({
    name: j.job_id?.slice(0, 8),
    pages: j.pages_crawled || 0,
    progress: j.progress_pct || 0,
  })) || []

  const openService = (key: string, val: Record<string, unknown>) => {
    const meta = SERVICE_META[key]
    openDetail({
      title: LABELS[key] || key,
      subtitle: meta?.layer,
      kind: 'service',
      serviceKey: key,
      logName: meta?.logName,
      healthUrl: meta?.healthUrl,
      data: { ...meta, health: val, status: val.status },
    })
  }

  const openJob = (job: Record<string, unknown>) => {
    openDetail({
      title: `Job ${String(job.job_id).slice(0, 12)}`,
      subtitle: String(job.requirement || '').slice(0, 80),
      kind: 'job',
      data: job,
    })
  }

  return (
    <div>
      <PageHeader title="Platform Overview" subtitle="Real-time health across all SpeedFlow layers — click any item for details & logs" />

      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
        <StatCard
          label="Services Online"
          value={loading && !overview ? <Skeleton className="h-10 w-20" /> : overview ? `${overview.services_up}/${overview.services_total}` : '—'}
          accent="emerald"
          onClick={() => overview && openDetail({
            title: 'All Services',
            kind: 'generic',
            data: { services: overview.services, timestamp: overview.timestamp },
          })}
        />
        <StatCard
          label="Active Scrape Jobs"
          value={jobs?.filter(j => j.status === 'running').length ?? 0}
          accent="cyan"
          onClick={() => navigate('/ingestion')}
        />
        <StatCard
          label="Completed Jobs"
          value={jobs?.filter(j => j.status === 'completed').length ?? 0}
          accent="violet"
          onClick={() => navigate('/ingestion')}
        />
      </div>

      {pipeline?.flow && (
        <Card className="mb-8">
          <h3 className="mb-4 text-lg font-semibold">Live Pipeline Flow</h3>
          <div className="flex flex-wrap gap-2">
            {pipeline.flow.map((step: { step: number; name: string; via: string }) => (
              <button
                key={step.step}
                type="button"
                onClick={() => openDetail({
                  title: step.name,
                  subtitle: step.via,
                  kind: 'pipeline',
                  data: step,
                  logName: step.name.includes('Crawlee') ? 'crawlee-worker' : step.name.includes('Stream') ? 'stream-processor' : undefined,
                })}
                className="rounded-xl bg-white/5 px-4 py-3 text-left transition hover:bg-accent-cyan/10 hover:ring-1 hover:ring-accent-cyan/30"
              >
                <span className="text-xs text-accent-cyan">Step {step.step}</span>
                <p className="text-sm font-semibold">{step.name}</p>
                <p className="text-[11px] text-white/40">{step.via}</p>
              </button>
            ))}
          </div>
        </Card>
      )}

      <Card className="mb-8">
        <h3 className="mb-4 text-lg font-semibold">Data Pipeline</h3>
        <PipelineFlow />
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-lg font-semibold">Service Health</h3>
          {loading && !overview && <p className="text-white/40">Loading…</p>}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {overview && Object.entries(overview.services).map(([key, val]: [string, any]) => (
              <ClickableRow key={key} onClick={() => openService(key, val)}>
                <span className="text-sm text-white/70">{LABELS[key] || key}</span>
                <StatusBadge status={val.status} />
              </ClickableRow>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Recent Crawl Progress</h3>
          <div className="h-48">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="gPages" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" stroke="#ffffff40" fontSize={11} />
                  <YAxis stroke="#ffffff40" fontSize={11} />
                  <Tooltip contentStyle={{ background: '#12121a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }} />
                  <Area type="monotone" dataKey="pages" stroke="#22d3ee" fill="url(#gPages)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-white/40">No scrape jobs yet</p>
            )}
          </div>
          {jobs?.slice(0, 3).map(job => (
            <ClickableRow key={job.job_id} onClick={() => openJob(job)} className="mt-2">
              <span className="font-mono text-accent-cyan">{job.job_id?.slice(0, 10)}</span>
              <StatusBadge status={job.status === 'completed' ? 'up' : job.status === 'failed' ? 'down' : 'degraded'} />
            </ClickableRow>
          ))}
        </Card>
      </div>
    </div>
  )
}
