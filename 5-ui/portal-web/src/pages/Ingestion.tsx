import { api } from '../api'
import { Card, ClickableRow, PageHeader, ProgressBar, StatusBadge, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'
import { SCRAPER_META, SERVICE_META } from '../lib/serviceMeta'

export default function Ingestion() {
  const { data: jobs } = usePoll(() => api.scrapeJobs())
  const { data: overview } = usePoll(() => api.overview())
  const { data: pipeline } = usePoll(() => api.pipeline())
  const { openDetail } = useDetail()

  const scrapers = Object.entries(SCRAPER_META).map(([id, meta]) => ({ id, ...meta }))

  const workerRunning = pipeline?.host_workers?.['crawlee-worker']?.running

  return (
    <div>
      <PageHeader title="Ingestion Edge" subtitle="Click scrapers, jobs, or workers for logs and full details" />

      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {scrapers.map(s => {
          const isCrawlee = s.id === 'crawlee-worker'
          const status = isCrawlee && workerRunning !== undefined
            ? (workerRunning ? 'up' : 'down')
            : 'degraded'
          return (
            <Card
              key={s.id}
              onClick={() => openDetail({
                title: s.label,
                subtitle: s.type,
                kind: 'scraper',
                logName: s.logName,
                healthUrl: s.healthUrl,
                data: { ...s, running: isCrawlee ? workerRunning : undefined },
              })}
              className="group"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-semibold">{s.label}</h4>
                  <p className="mt-1 text-xs text-white/40">{s.type}</p>
                </div>
                <StatusBadge status={status} />
              </div>
              <p className="mt-3 text-xs text-white/50">Container: {s.container || 'host process'}</p>
              <p className="mt-2 text-xs text-accent-cyan/0 transition group-hover:text-accent-cyan/80">View details & logs →</p>
            </Card>
          )
        })}
      </div>

      <Card>
        <h3 className="mb-4 text-lg font-semibold">Crawlee Job Queue</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 text-white/50">
                <th className="pb-3 pr-4">Job ID</th>
                <th className="pb-3 pr-4">Tenant</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Progress</th>
                <th className="pb-3 pr-4">Pages</th>
                <th className="pb-3">Requirement</th>
              </tr>
            </thead>
            <tbody>
              {jobs?.map(job => (
                <tr
                  key={job.job_id}
                  className="clickable-table-row border-b border-white/5"
                  onClick={() => openDetail({
                    title: `Scrape Job ${job.job_id}`,
                    subtitle: job.tenant_name || job.tenant_id,
                    kind: 'job',
                    logName: 'crawlee-worker',
                    data: job,
                  })}
                >
                  <td className="py-3 pr-4 font-mono text-accent-cyan">{job.job_id?.slice(0, 12)}</td>
                  <td className="py-3 pr-4">{job.tenant_name || job.tenant_id}</td>
                  <td className="py-3 pr-4">
                    <StatusBadge status={job.status === 'completed' ? 'up' : job.status === 'failed' ? 'down' : 'degraded'} />
                    <span className="ml-2 text-xs">{job.status}</span>
                  </td>
                  <td className="w-40 py-3 pr-4">
                    <ProgressBar value={job.progress_pct || 0} />
                    <span className="text-xs text-white/40">{job.progress_pct || 0}%</span>
                  </td>
                  <td className="py-3 pr-4">{job.pages_crawled || 0}</td>
                  <td className="max-w-xs truncate py-3 text-white/60">{job.requirement}</td>
                </tr>
              ))}
              {!jobs?.length && (
                <tr><td colSpan={6} className="py-8 text-center text-white/40">No jobs yet — create a tenant and submit a scrape</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {overview && (
        <Card
          className="mt-6"
          onClick={() => {
            const meta = SERVICE_META.schema_registry
            openDetail({
              title: meta.label,
              kind: 'service',
              healthUrl: meta.healthUrl,
              data: { ...meta, health: overview.services?.schema_registry },
            })
          }}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-white/50">Avro Schema Registry</h3>
            <StatusBadge status={overview.services?.schema_registry?.status || 'down'} />
          </div>
          <p className="mt-2 text-xs text-white/35">Click for schema & health details</p>
        </Card>
      )}
    </div>
  )
}
