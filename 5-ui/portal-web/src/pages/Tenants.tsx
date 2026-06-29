import { useState } from 'react'
import { api } from '../api'
import { Card, ClickableRow, PageHeader, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'

export default function Tenants() {
  const { data: tenants, refresh } = usePoll(() => api.tenants())
  const { data: plansData } = usePoll(() => api.plans())
  const [name, setName] = useState('Demo Corp')
  const [plan, setPlan] = useState('pro')
  const [apiKey, setApiKey] = useState('')
  const [requirement, setRequirement] = useState('Scrape titles from https://news.ycombinator.com')
  const [message, setMessage] = useState('')
  const { openDetail } = useDetail()

  const createTenant = async () => {
    try {
      const t = await api.createTenant({ name, plan, email: `${name.toLowerCase().replace(/\s/g, '')}@demo.local` })
      setApiKey(t.api_key)
      setMessage(`Created tenant ${t.tenant_id} — API key copied below`)
      refresh()
    } catch (e) {
      setMessage(String(e))
    }
  }

  const submitScrape = async () => {
    if (!apiKey) { setMessage('Create or paste an API key first'); return }
    try {
      const job = await api.scrape({ requirement, api_key: apiKey, max_pages: 10 })
      setMessage(`Scrape job queued: ${job.job_id}`)
    } catch (e) {
      setMessage(String(e))
    }
  }

  const plans = plansData?.plans ? Object.entries(plansData.plans) : []

  return (
    <div>
      <PageHeader title="Tenants & Subscriptions" subtitle="Click tenants or plans for quotas, features, and API details" />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-lg font-semibold">Create Tenant</h3>
          <div className="space-y-3">
            <input
              className="input-field"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Company name"
            />
            <select className="input-field" value={plan} onChange={e => setPlan(e.target.value)}>
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>
            <button type="button" onClick={createTenant} className="btn-action-primary w-full">
              Create Tenant
            </button>
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Submit Scrape Job</h3>
          <div className="space-y-3">
            <input
              className="input-field font-mono text-xs"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="X-API-Key (sf_...)"
            />
            <textarea
              className="input-field"
              rows={3}
              value={requirement}
              onChange={e => setRequirement(e.target.value)}
            />
            <button type="button" onClick={submitScrape} className="btn-action-secondary w-full">
              Submit Scrape
            </button>
          </div>
          {message && <p className="mt-3 text-sm text-white/60">{message}</p>}
        </Card>
      </div>

      <Card className="mt-8">
        <h3 className="mb-4 text-lg font-semibold">Subscription Plans</h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {plans.map(([key, p]: [string, any]) => (
            <button
              key={key}
              type="button"
              onClick={() => openDetail({
                title: p.name || key,
                subtitle: `$${p.price_usd_monthly}/mo`,
                kind: 'tenant',
                data: { plan: key, ...p },
              })}
              className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-left transition hover:border-accent-violet/40 hover:bg-white/[0.05] hover:shadow-lg hover:shadow-accent-violet/10"
            >
              <h4 className="font-semibold capitalize">{p.name || key}</h4>
              <p className="text-2xl font-bold text-accent-violet">${p.price_usd_monthly}<span className="text-sm text-white/40">/mo</span></p>
              <ul className="mt-3 space-y-1 text-xs text-white/50">
                <li>{p.limits?.scrape_requests_per_day} scrapes/day</li>
                <li>{p.limits?.max_pages_per_job} pages/job</li>
                <li>Proxy: {p.features?.proxy ? '✓' : '—'}</li>
              </ul>
              <p className="mt-3 text-xs text-accent-cyan/0 transition hover:text-accent-cyan/80">View full plan →</p>
            </button>
          ))}
        </div>
      </Card>

      <Card className="mt-8">
        <h3 className="mb-4 text-lg font-semibold">Registered Tenants</h3>
        <div className="space-y-1">
          {tenants?.map(t => (
            <ClickableRow
              key={t.tenant_id}
              onClick={() => openDetail({
                title: t.name,
                subtitle: t.tenant_id,
                kind: 'tenant',
                data: t,
              })}
            >
              <span className="font-mono text-accent-cyan">{t.tenant_id}</span>
              <span>{t.name}</span>
              <span className="capitalize text-white/50">{t.plan}</span>
            </ClickableRow>
          ))}
          {!tenants?.length && <p className="py-4 text-center text-white/40">No tenants yet</p>}
        </div>
      </Card>
    </div>
  )
}
