import { ArrowRight, Database, Radio, Server } from 'lucide-react'
import { useDetail } from '../context/DetailContext'
import { HOST_WORKERS, PIPELINE_STAGES, SCRAPER_META, SERVICE_META } from '../lib/serviceMeta'

const ICONS: Record<string, typeof Radio> = {
  ingestion: Radio,
  messaging: Server,
  compute: Server,
  storage: Database,
}

export default function PipelineFlow() {
  const { openDetail } = useDetail()

  const openItem = (item: { id: string; label: string; topic?: boolean; port?: number }) => {
    if (item.topic) {
      openDetail({
        title: item.label,
        subtitle: 'Kafka topic',
        kind: 'topic',
        data: {
          description: `Events flow through ${item.label} with Avro serialization via Schema Registry.`,
          layer: 'Messaging',
        },
      })
      return
    }
    if (item.id === 'postgres') {
      openDetail({
        title: 'PostgreSQL',
        subtitle: 'platform_db',
        kind: 'service',
        data: { description: 'Tenants, scrape_jobs, Airflow metadata', layer: 'Storage', port: 5433, container: 'platform-postgres' },
        healthUrl: undefined,
      })
      return
    }
    const meta = SERVICE_META[item.id] || HOST_WORKERS[item.id] || SCRAPER_META[item.id]
    if (meta) {
      openDetail({
        title: meta.label,
        subtitle: meta.layer,
        kind: item.id in SCRAPER_META ? 'scraper' : 'service',
        logName: meta.logName,
        healthUrl: meta.healthUrl,
        serviceKey: item.id,
        data: { ...meta },
      })
    }
  }

  const openStage = (stage: (typeof PIPELINE_STAGES)[0]) => {
    openDetail({
      title: stage.label,
      subtitle: 'Pipeline stage',
      kind: 'pipeline',
      data: {
        description: `${stage.items.length} components in this layer`,
        layer: stage.label,
        items: stage.items.map(i => i.label),
      },
    })
  }

  return (
    <div className="flex flex-wrap items-stretch justify-center gap-3 lg:gap-2">
      {PIPELINE_STAGES.map((stage, i) => {
        const Icon = ICONS[stage.id] || Server
        return (
          <div key={stage.id} className="flex items-center">
            <button type="button" onClick={() => openStage(stage)} className="pipeline-node w-52 text-left">
              <div className={`mb-3 inline-flex rounded-lg bg-gradient-to-br ${stage.color} p-2 shadow-lg`}>
                <Icon className="h-4 w-4 text-white" />
              </div>
              <h4 className="text-sm font-semibold">{stage.label}</h4>
              <ul className="mt-2 space-y-1">
                {stage.items.map(item => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={e => { e.stopPropagation(); openItem(item) }}
                      className="w-full rounded-md px-1 py-0.5 text-left text-xs text-white/45 transition hover:bg-white/10 hover:text-accent-cyan"
                    >
                      {item.label} →
                    </button>
                  </li>
                ))}
              </ul>
            </button>
            {i < PIPELINE_STAGES.length - 1 && (
              <ArrowRight className="mx-1 hidden h-5 w-5 shrink-0 text-white/20 lg:block" />
            )}
          </div>
        )
      })}
    </div>
  )
}
