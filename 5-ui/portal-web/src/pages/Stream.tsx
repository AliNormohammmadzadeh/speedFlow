import { api } from '../api'
import { Card, ClickableRow, PageHeader, StatusBadge, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'
import { HOST_WORKERS, SERVICE_META } from '../lib/serviceMeta'

export default function Stream() {
  const { data: overview } = usePoll(() => api.overview())
  const { data: connectors } = usePoll(() => api.connectors())
  const { data: schemas } = usePoll(() => api.schemas())
  const { data: metrics } = usePoll(() => api.dashboardMetrics())
  const { data: pipeline } = usePoll(() => api.pipeline())
  const { openDetail } = useDetail()

  const openSvc = (key: string, extra?: Record<string, unknown>) => {
    const meta = SERVICE_META[key] || HOST_WORKERS[key]
    openDetail({
      title: meta?.label || key,
      kind: 'service',
      logName: meta?.logName,
      healthUrl: meta?.healthUrl,
      data: { ...meta, health: overview?.services?.[key], ...extra },
    })
  }

  const streamProcRunning = pipeline?.host_workers?.['stream-processor']?.running

  return (
    <div>
      <PageHeader title="Stream Compute" subtitle="Kafka, Flink, ML inference — click any component for health & logs" />

      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          { label: 'Stream Processor', key: 'stream-processor', desc: 'raw_stream → processed_stream', host: true },
          { label: 'Flink Cluster', key: 'flink', desc: 'Stateful stream jobs' },
          { label: 'ML Service', key: 'ml_service', desc: 'sklearn / CUDA inference' },
        ].map(item => (
          <Card key={item.label} onClick={() => openSvc(item.key, item.host ? { running: streamProcRunning } : undefined)} className="group">
            <h4 className="font-semibold">{item.label}</h4>
            <p className="mt-1 text-xs text-white/40">{item.desc}</p>
            <div className="mt-3">
              <StatusBadge
                status={
                  item.host
                    ? (streamProcRunning ? 'up' : 'down')
                    : (overview?.services?.[item.key]?.status || 'down')
                }
              />
            </div>
            <p className="mt-3 text-xs text-white/30 group-hover:text-accent-cyan/70">Click for details →</p>
          </Card>
        ))}
      </div>

      {pipeline?.topics && (
        <Card className="mb-8">
          <h3 className="mb-3 text-lg font-semibold">Kafka Topics</h3>
          <div className="flex flex-wrap gap-2">
            {pipeline.topics.map((t: string) => (
              <button
                key={t}
                type="button"
                onClick={() => openDetail({ title: t, kind: 'topic', data: { description: 'Kafka topic in SpeedFlow pipeline', layer: 'Messaging' } })}
                className="rounded-lg bg-white/5 px-4 py-2 font-mono text-sm text-accent-cyan transition hover:bg-accent-cyan/10 hover:ring-1 hover:ring-accent-cyan/30"
              >
                {t}
              </button>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-lg font-semibold">Kafka Connect Sinks</h3>
          {connectors?.connectors?.length ? connectors.connectors.map((c: any) => (
            <ClickableRow
              key={c.name}
              onClick={() => openDetail({ title: c.name, kind: 'connector', data: c })}
              className="mb-2"
            >
              <div>
                <span className="font-medium">{c.name}</span>
                <p className="text-xs text-white/40">
                  Tasks: {c.status?.tasks?.map((t: any) => t.state).join(', ') || '—'}
                </p>
              </div>
              <StatusBadge status={c.status?.connector?.state === 'RUNNING' ? 'up' : 'degraded'} />
            </ClickableRow>
          )) : (
            <button
              type="button"
              onClick={() => openSvc('kafka_connect')}
              className="w-full rounded-xl bg-white/5 p-4 text-left text-sm text-white/40 transition hover:bg-white/10"
            >
              No connectors registered — click for Kafka Connect status
            </button>
          )}
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Avro Schemas</h3>
          <ul className="space-y-2">
            {schemas?.subjects?.map((s: string) => (
              <li key={s}>
                <ClickableRow onClick={() => openDetail({ title: s, kind: 'schema', data: { subject: s, registry: SERVICE_META.schema_registry } })}>
                  <span className="font-mono text-accent-cyan">{s}</span>
                </ClickableRow>
              </li>
            )) || <p className="text-white/40">No schemas registered</p>}
          </ul>
        </Card>

        <Card className="lg:col-span-2">
          <h3 className="mb-4 text-lg font-semibold">Processed Events (Elasticsearch)</h3>
          <div className="grid grid-cols-3 gap-4">
            <Card onClick={() => openDetail({ title: 'Indexed Events', kind: 'generic', data: metrics || {} })}>
              <p className="text-2xl font-bold text-accent-cyan">{metrics?.events_indexed ?? metrics?.total_events ?? 0}</p>
              <p className="text-xs text-white/40">Indexed Events</p>
            </Card>
            <Card onClick={() => openSvc('elasticsearch')}>
              <StatusBadge status={overview?.services?.elasticsearch?.status || 'down'} />
              <p className="mt-2 text-xs text-white/40">Elasticsearch</p>
            </Card>
            <Card onClick={() => openSvc('kafka_connect')}>
              <StatusBadge status={overview?.services?.kafka_connect?.status || 'down'} />
              <p className="mt-2 text-xs text-white/40">Connect</p>
            </Card>
          </div>
        </Card>
      </div>
    </div>
  )
}
