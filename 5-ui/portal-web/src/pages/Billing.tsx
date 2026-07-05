import { useState } from 'react'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Card, PageHeader, ProgressBar, usePoll } from '../components/ui'

export default function Billing() {
  const [apiKey, setApiKey] = useState('')
  const [plan, setPlan] = useState('pro')
  const [invoice, setInvoice] = useState<any>(null)
  const [analytics, setAnalytics] = useState<any>(null)
  const [myLimit, setMyLimit] = useState<any>(null)
  const [message, setMessage] = useState('')
  const { data: rl } = usePoll(() => api.rateLimits(), 5000)

  const loadTenant = async () => {
    if (!apiKey) { setMessage('Paste a tenant API key (sf_...) first'); return }
    setMessage('')
    try {
      const [inv, an, me] = await Promise.all([
        api.billingInvoice(apiKey),
        api.usageAnalytics(apiKey, 30),
        api.rateLimitMe(apiKey),
      ])
      setInvoice(inv); setAnalytics(an); setMyLimit(me)
    } catch (e) {
      setMessage(String(e))
    }
  }

  const upgrade = async () => {
    if (!apiKey) { setMessage('Paste a tenant API key first'); return }
    try {
      const r = await api.changePlan(apiKey, plan)
      setMessage(`Plan changed: ${r.old_plan} → ${r.new_plan}`)
      loadTenant()
    } catch (e) {
      setMessage(String(e))
    }
  }

  const series = (analytics?.series ?? []).map((s: any) => ({ day: s.day?.slice(5), cost: s.cost_usd }))
  const tenants = rl?.tenants ?? []

  return (
    <div>
      <PageHeader title="Billing & Usage" subtitle="Self-serve billing, usage analytics, plan upgrades, and platform rate limits" />

      <Card className="mb-6">
        <h3 className="mb-4 text-lg font-semibold">Tenant Self-Serve</h3>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="input-field font-mono text-xs sm:flex-1"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="Tenant API key (sf_...)"
          />
          <button type="button" onClick={loadTenant} className="btn-action-primary px-6 sm:w-auto">
            Load Account
          </button>
        </div>
        {message && <p className="mt-3 text-sm text-white/60">{message}</p>}
      </Card>

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-lg font-semibold">Current Invoice</h3>
          {invoice ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-white/50">Period</span><span>{invoice.period}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-white/50">Base fee</span><span>${invoice.breakdown?.base_fee_usd ?? 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-white/50">Metered usage</span><span>${invoice.breakdown?.usage_total_usd ?? 0}</span>
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3">
                <span className="font-semibold">Total due</span>
                <span className="text-2xl font-bold text-accent-cyan">${invoice.amount_usd}</span>
              </div>
            </div>
          ) : (
            <p className="text-white/40">Load an account to see the current invoice.</p>
          )}
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Change Plan</h3>
          <div className="space-y-3">
            <select className="input-field" value={plan} onChange={e => setPlan(e.target.value)}>
              <option value="starter">Starter — $49/mo</option>
              <option value="pro">Pro — $299/mo</option>
              <option value="enterprise">Enterprise — $1499/mo</option>
            </select>
            <button type="button" onClick={upgrade} className="btn-action-secondary w-full">
              Upgrade / Downgrade Plan
            </button>
            {myLimit && (
              <div className="rounded-xl bg-white/5 p-3 text-sm">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-white/50">Daily scrape quota ({myLimit.plan})</span>
                  <span className="font-mono">{myLimit.used}/{myLimit.limit}</span>
                </div>
                <ProgressBar value={myLimit.utilization_pct} />
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card className="mb-6">
        <h3 className="mb-4 text-lg font-semibold">Usage Analytics — Last 30 Days</h3>
        <div className="h-56">
          {series.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="gCost" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" stroke="#ffffff40" fontSize={11} />
                <YAxis stroke="#ffffff40" fontSize={11} />
                <Tooltip contentStyle={{ background: '#12121a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }} />
                <Area type="monotone" dataKey="cost" name="USD" stroke="#a78bfa" fill="url(#gCost)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-white/40">Load an account with metered usage to see the cost trend.</p>
          )}
        </div>
        {analytics?.by_category && Object.keys(analytics.by_category).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(analytics.by_category).map(([cat, v]: [string, any]) => (
              <span key={cat} className="rounded-full bg-white/5 px-3 py-1 text-xs text-white/60">
                {cat}: {v.units} units · ${v.cost_usd}
              </span>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">API Rate Limits — Platform-wide</h3>
          {rl && <span className="text-xs text-white/40">{rl.throttled?.length ?? 0} throttled · {rl.count} tenants</span>}
        </div>
        <div className="space-y-2">
          {tenants.slice(0, 15).map((t: any) => (
            <div key={t.tenant_id} className="rounded-xl bg-white/5 p-3">
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="truncate">
                  <span className="font-mono text-accent-cyan">{t.tenant_id}</span>
                  <span className="ml-2 text-white/60">{t.name}</span>
                  <span className="ml-2 capitalize text-white/40">({t.plan})</span>
                </span>
                <span className={`font-mono ${t.remaining === 0 ? 'text-red-400' : 'text-white/70'}`}>
                  {t.used}/{t.limit}
                </span>
              </div>
              <ProgressBar value={t.utilization_pct} />
            </div>
          ))}
          {!tenants.length && <p className="py-4 text-center text-white/40">No tenants yet</p>}
        </div>
      </Card>
    </div>
  )
}
