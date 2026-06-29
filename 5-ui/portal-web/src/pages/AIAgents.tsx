import { useState } from 'react'
import { api } from '../api'
import { Card, ClickableRow, PageHeader, StatusBadge, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'

const AGENTS = [
  { name: 'Strategy', id: 'strategy', desc: 'Business goals → data gaps' },
  { name: 'Discovery', id: 'discovery', desc: 'Source valuation & targets' },
  { name: 'Processing', id: 'processing', desc: 'Flink vs ML routing' },
  { name: 'Config', id: 'config', desc: 'Terraform / GitOps output' },
  { name: 'Scrape Planner', id: 'scrape_planner', desc: 'NL requirements → Crawlee params' },
]

const BRIDGES = [
  { name: 'Scraper Bridge', desc: 'Redis → Crawlee job queue', queue: 'crawlee:jobs' },
  { name: 'Processing Bridge', desc: 'ML config + Flink job queue', queue: 'processing:jobs' },
  { name: 'Config Bridge', desc: 'GitOps manifest output', queue: 'gitops-output/' },
]

export default function AIAgents() {
  const { data: agents } = usePoll(() => api.agents())
  const [orchestrating, setOrchestrating] = useState(false)
  const [result, setResult] = useState<any>(null)
  const { openDetail } = useDetail()

  const runCycle = async () => {
    setOrchestrating(true)
    try {
      setResult(await api.orchestrate())
    } catch (e) {
      setResult({ error: String(e) })
    } finally {
      setOrchestrating(false)
    }
  }

  return (
    <div>
      <PageHeader title="AI Intelligence" subtitle="Click agents & bridges for status — orchestration logs in drawer" />

      <Card className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold">Run Orchestration Cycle</h3>
            <p className="text-sm text-white/50">Strategy → Discovery → Processing → Config → Bridges</p>
          </div>
          <button
            type="button"
            onClick={runCycle}
            disabled={orchestrating}
            className="btn-action-primary"
          >
            {orchestrating ? 'Running…' : 'Orchestrate Now'}
          </button>
        </div>
        {result && (
          <button
            type="button"
            onClick={() => openDetail({
              title: 'Orchestration Result',
              kind: 'generic',
              logName: 'orchestrator',
              data: result,
            })}
            className="mt-4 w-full rounded-xl bg-black/40 p-4 text-left transition hover:bg-black/60"
          >
            <p className="text-xs text-accent-cyan">Click to expand full result & logs</p>
            <pre className="mt-2 max-h-24 overflow-hidden text-xs text-white/70">
              {JSON.stringify(result, null, 2).slice(0, 300)}…
            </pre>
          </button>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {AGENTS.map(agent => {
          const live = agents?.find(a => a.agent === agent.id)
          return (
            <Card
              key={agent.id}
              onClick={() => openDetail({
                title: agent.name,
                subtitle: agent.desc,
                kind: 'agent',
                logName: agent.id === 'scrape_planner' ? 'orchestrator' : 'orchestrator',
                data: { ...agent, live },
              })}
              className="group"
            >
              <div className="flex items-start justify-between">
                <h4 className="font-semibold">{agent.name}</h4>
                <StatusBadge status={live?.status === 'ready' ? 'up' : 'degraded'} />
              </div>
              <p className="mt-2 text-sm text-white/50">{agent.desc}</p>
              <p className="mt-3 text-xs text-white/30 group-hover:text-accent-cyan/70">View agent details →</p>
            </Card>
          )
        })}
      </div>

      <Card className="mt-8">
        <h3 className="mb-4 text-lg font-semibold">AI Bridges</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {BRIDGES.map(b => (
            <ClickableRow
              key={b.name}
              onClick={() => openDetail({
                title: b.name,
                subtitle: b.queue,
                kind: 'pipeline',
                logName: b.name.includes('Scraper') ? 'crawlee-worker' : 'orchestrator',
                data: b,
              })}
            >
              <div className="text-left">
                <p className="font-medium">{b.name}</p>
                <p className="text-xs text-white/40">{b.desc}</p>
              </div>
            </ClickableRow>
          ))}
        </div>
      </Card>
    </div>
  )
}
