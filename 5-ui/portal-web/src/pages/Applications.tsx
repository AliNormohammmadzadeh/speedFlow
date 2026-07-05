import { useState } from 'react'
import { Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Card, ClickableRow, PageHeader, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'
import { SERVICE_META } from '../lib/serviceMeta'

export default function Applications() {
  const { data: signals } = usePoll(() => api.tradingSignals())
  const { data: stats } = usePoll(() => api.tradingStats())
  const { data: products } = usePoll(() => api.marketplaceProducts())
  const { data: metrics } = usePoll(() => api.dashboardMetrics())
  const { data: timeseries } = usePoll(() => api.dashboardTimeseries())
  const { data: byVertical } = usePoll(() => api.dashboardByVertical())
  const { data: overview } = usePoll(() => api.overview())
  const { data: datasets, refresh: refreshDatasets } = usePoll(() => api.datasets(), 5000)
  const { openDetail } = useDetail()

  const [dsName, setDsName] = useState('BTC Order-Book Snapshots')
  const [dsPrice, setDsPrice] = useState(49)
  const [dsShare, setDsShare] = useState(70)
  const [dsMsg, setDsMsg] = useState('')

  const publishDataset = async () => {
    try {
      const r = await api.publishDataset({
        publisher_tenant: 'demo-tenant', name: dsName,
        description: 'Tenant-published dataset', price_usd: Number(dsPrice),
        revenue_share_pct: Number(dsShare), vertical: 'financial_markets',
      })
      setDsMsg(`Published ${r.dataset_id} (${r.revenue_share_pct}% to publisher)`)
      refreshDatasets()
    } catch (e) {
      setDsMsg(String(e))
    }
  }

  const buyDataset = async (id: string) => {
    try {
      const r = await api.purchaseDataset(id, { buyer_id: 'demo-buyer' })
      const rev = await api.datasetRevenue(id)
      openDetail({ title: 'Purchase complete', subtitle: id, kind: 'generic', data: { sale: r, revenue_report: rev } })
      refreshDatasets()
    } catch (e) {
      setDsMsg(String(e))
    }
  }

  const tsData = (timeseries?.series ?? []).map((b: any) => ({
    time: new Date(b.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    count: b.count,
  }))
  const vData = (byVertical?.verticals ?? []).map((v: any) => ({ vertical: v.vertical, count: v.count }))

  const openApp = (key: keyof typeof SERVICE_META) => {
    const meta = SERVICE_META[key]
    openDetail({
      title: meta.label,
      kind: 'service',
      logName: meta.logName,
      healthUrl: meta.healthUrl,
      data: { ...meta, health: overview?.services?.[key] },
    })
  }

  return (
    <div>
      <PageHeader title="End-Use Applications" subtitle="Click any app, signal, or metric for full details" />

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card onClick={() => openApp('dashboard')}>
          <h3 className="mb-4 text-lg font-semibold">Processed Events — Last 24h (ES)</h3>
          <div className="h-56">
            {tsData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={tsData}>
                  <defs>
                    <linearGradient id="gEvents" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" stroke="#ffffff40" fontSize={11} />
                  <YAxis stroke="#ffffff40" fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#12121a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }} />
                  <Area type="monotone" dataKey="count" stroke="#22d3ee" fill="url(#gEvents)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-white/40">No indexed events yet</p>
            )}
          </div>
        </Card>

        <Card onClick={() => openApp('dashboard')}>
          <h3 className="mb-4 text-lg font-semibold">Events by Vertical (ES)</h3>
          <div className="h-56">
            {vData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={vData}>
                  <XAxis dataKey="vertical" stroke="#ffffff40" fontSize={10} />
                  <YAxis stroke="#ffffff40" fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#12121a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }} />
                  <Bar dataKey="count" fill="#a78bfa" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-white/40">No indexed events yet</p>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card onClick={() => openApp('trading_bot')} className="group">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Trading Bot — Live Signals
          </h3>
          {stats && (
            <div className="mb-4 grid grid-cols-3 gap-2 text-center">
              {[
                { label: 'PnL', value: `$${stats.pnl_usd?.toFixed(2) ?? '0'}`, key: 'pnl' },
                { label: 'Win Rate', value: stats.win_rate ?? '—', key: 'win' },
                { label: 'Signals', value: stats.total_signals ?? 0, key: 'sig' },
              ].map(item => (
                <button
                  key={item.key}
                  type="button"
                  onClick={e => { e.stopPropagation(); openDetail({ title: item.label, kind: 'generic', data: stats }) }}
                  className="rounded-lg bg-white/5 p-2 transition hover:bg-accent-cyan/10"
                >
                  <p className="text-lg font-bold text-accent-cyan">{item.value}</p>
                  <p className="text-xs text-white/40">{item.label}</p>
                </button>
              ))}
            </div>
          )}
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {signals?.slice(0, 10).map((s: any, i: number) => (
              <ClickableRow key={i} onClick={() => openDetail({ title: s.symbol || 'Signal', kind: 'generic', data: s })}>
                <span className="font-mono text-white/70">{s.symbol}</span>
                <span className={s.signal_type === 'buy' ? 'text-emerald-400' : s.signal_type === 'sell' ? 'text-red-400' : 'text-white/50'}>
                  {s.signal_type?.toUpperCase()}
                </span>
                <span className="text-white/40">{s.price ?? '—'}</span>
              </ClickableRow>
            )) || <p className="text-white/40">No signals yet — click card for service health</p>}
          </div>
        </Card>

        <Card onClick={() => openApp('dashboard')} className="group">
          <h3 className="mb-4 text-lg font-semibold">Meta Dashboard</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Daily Active Users', value: metrics?.daily_active_users ?? 42 },
              { label: 'Events Indexed', value: metrics?.events_indexed ?? metrics?.total_events ?? 0 },
              { label: 'Query P95', value: `${metrics?.query_latency_p95 ?? 120}ms` },
              { label: 'Engagement', value: `${metrics?.engagement_minutes ?? 15}m` },
            ].map(m => (
              <button
                key={m.label}
                type="button"
                onClick={e => { e.stopPropagation(); openDetail({ title: m.label, kind: 'generic', data: metrics || {} }) }}
                className="rounded-xl bg-white/5 p-4 text-left transition hover:bg-white/10 hover:ring-1 hover:ring-accent-violet/30"
              >
                <p className="text-2xl font-bold">{m.value}</p>
                <p className="text-xs text-white/40">{m.label}</p>
              </button>
            ))}
          </div>
        </Card>

        <Card onClick={() => openApp('marketplace')}>
          <h3 className="mb-4 text-lg font-semibold">Data Marketplace</h3>
          <div className="space-y-2">
            {(Array.isArray(products) ? products : products?.products || []).slice(0, 6).map((p: any) => (
              <ClickableRow key={p.id || p.product_id} onClick={() => openDetail({ title: p.name || p.id, kind: 'generic', data: p })}>
                <span>{p.name || p.id}</span>
                <span className="text-accent-cyan">${p.price_usd ?? p.price ?? '—'}</span>
              </ClickableRow>
            )) || <p className="text-white/40">No products — click for marketplace service status</p>}
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Publish & Sell Datasets</h3>
          <div className="mb-4 space-y-2">
            <input className="input-field" value={dsName} onChange={e => setDsName(e.target.value)} placeholder="Dataset name" />
            <div className="flex gap-2">
              <input className="input-field" type="number" value={dsPrice} onChange={e => setDsPrice(Number(e.target.value))} placeholder="Price USD" />
              <input className="input-field" type="number" value={dsShare} onChange={e => setDsShare(Number(e.target.value))} placeholder="Revenue share %" />
            </div>
            <button type="button" onClick={publishDataset} className="btn-action-primary w-full">Publish Dataset</button>
            {dsMsg && <p className="text-sm text-white/60">{dsMsg}</p>}
          </div>
          <div className="max-h-52 space-y-2 overflow-y-auto">
            {(datasets?.datasets ?? []).map((d: any) => (
              <div key={d.dataset_id} className="flex items-center gap-2 rounded-xl bg-white/5 p-2 text-sm">
                <span className="min-w-0 flex-1 truncate">{d.name}</span>
                <span className="text-white/40">{d.sales_count} sold</span>
                <span className="text-accent-cyan">${d.price_usd}</span>
                <button type="button" onClick={() => buyDataset(d.dataset_id)} className="btn-action-secondary px-3 py-1 text-xs">Buy</button>
              </div>
            ))}
            {!(datasets?.datasets ?? []).length && <p className="py-3 text-center text-white/40">No datasets published yet</p>}
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Other Apps</h3>
          <div className="space-y-3">
            {[
              { name: 'Accommodation Aggregator', key: 'aggregator' as const, port: 8010, path: '/search?location=Paris' },
              { name: 'Auditing Service', key: 'auditing' as const, port: 8012, path: '/audit' },
            ].map(app => (
              <div key={app.name} className="flex gap-2">
                <button
                  type="button"
                  onClick={() => openApp(app.key)}
                  className="clickable-row flex-1"
                >
                  <span>{app.name}</span>
                  <span className="text-xs text-white/40">:{app.port}</span>
                </button>
                <a
                  href={`http://localhost:${app.port}${app.path}`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn-icon shrink-0"
                  title="Open app"
                >
                  ↗
                </a>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
