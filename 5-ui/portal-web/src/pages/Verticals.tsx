import { useState } from 'react'
import { api } from '../api'
import { Card, ClickableRow, PageHeader, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'

const SOURCE_BADGE: Record<string, string> = {
  core: 'bg-cyan-500/15 text-cyan-300 ring-cyan-500/30',
  plugin: 'bg-violet-500/15 text-violet-300 ring-violet-500/30',
  runtime: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
}

export default function Verticals() {
  const { data, refresh } = usePoll(() => api.verticals(), 5000)
  const { openDetail } = useDetail()
  const [id, setId] = useState('healthcare')
  const [name, setName] = useState('Healthcare & Pharma')
  const [description, setDescription] = useState('Drug prices, clinical trials, provider directories')
  const [sourceUrl, setSourceUrl] = useState('https://clinicaltrials.gov/api/v2/studies')
  const [message, setMessage] = useState('')

  const register = async () => {
    if (!id || !name) { setMessage('id and name are required'); return }
    try {
      const body = {
        id, name, description, priority: 10,
        seed_sources: sourceUrl ? [{ name: `${id}_source`, type: 'rest', url: sourceUrl, value_score: 0.7 }] : [],
        target_apps: ['meta_dashboard'],
      }
      const r = await api.registerVertical(body)
      setMessage(`Registered vertical: ${r.vertical?.id}`)
      refresh()
    } catch (e) {
      setMessage(String(e))
    }
  }

  const verticals = data?.verticals ?? []

  return (
    <div>
      <PageHeader title="Vertical Plug-in Framework" subtitle="Extend SpeedFlow to new industries — core, plug-in files, or runtime registration" />

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-lg font-semibold">Register a Vertical Plug-in</h3>
          <div className="space-y-3">
            <input className="input-field" value={id} onChange={e => setId(e.target.value)} placeholder="vertical id (e.g. healthcare)" />
            <input className="input-field" value={name} onChange={e => setName(e.target.value)} placeholder="Display name" />
            <textarea className="input-field" rows={2} value={description} onChange={e => setDescription(e.target.value)} placeholder="Description" />
            <input className="input-field" value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} placeholder="Seed source URL (optional)" />
            <button type="button" onClick={register} className="btn-action-primary w-full">Register Vertical</button>
          </div>
          {message && <p className="mt-3 text-sm text-white/60">{message}</p>}
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Framework</h3>
          <ul className="space-y-3 text-sm text-white/70">
            <li><span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-xs text-cyan-300 ring-1 ring-cyan-500/30">core</span> — shipped in <span className="font-mono text-xs">config/business/verticals.yaml</span></li>
            <li><span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-xs text-violet-300 ring-1 ring-violet-500/30">plugin</span> — drop-in YAML in <span className="font-mono text-xs">config/verticals/*.yaml</span></li>
            <li><span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300 ring-1 ring-emerald-500/30">runtime</span> — registered here, persisted to Redis</li>
          </ul>
          {data && (
            <p className="mt-4 text-sm text-white/50">
              {data.count} verticals loaded from {(data.sources ?? []).join(', ') || 'core'}.
            </p>
          )}
        </Card>
      </div>

      <Card>
        <h3 className="mb-4 text-lg font-semibold">Registered Verticals</h3>
        <div className="space-y-1">
          {verticals.map((v: any) => (
            <ClickableRow
              key={v.id}
              onClick={() => openDetail({ title: v.name, subtitle: v.id, kind: 'generic', data: v })}
            >
              <span className="font-medium">{v.name}</span>
              <span className="hidden text-white/40 sm:inline">{v.description}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs ring-1 ${SOURCE_BADGE[v.source] || SOURCE_BADGE.core}`}>{v.source}</span>
            </ClickableRow>
          ))}
          {!verticals.length && <p className="py-4 text-center text-white/40">No verticals loaded</p>}
        </div>
      </Card>
    </div>
  )
}
