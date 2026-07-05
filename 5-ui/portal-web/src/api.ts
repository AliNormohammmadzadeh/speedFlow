const BASE = '/api'

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export const api = {
  overview: () => fetchJson<any>('/overview'),
  scrapeJobs: () => fetchJson<any[]>('/scrape-jobs'),
  tenants: () => fetchJson<any[]>('/tenants'),
  createTenant: (body: object) => fetchJson<any>('/tenants', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  scrape: (body: object) => fetchJson<any>('/scrape', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  orchestrate: () => fetchJson<any>('/orchestrate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ business_goals: ['maximize_revenue'], run_bridges: true }) }),
  agents: () => fetchJson<any[]>('/agents'),
  tradingSignals: () => fetchJson<any[]>('/trading/signals'),
  tradingStats: () => fetchJson<any>('/trading/stats'),
  marketplaceProducts: () => fetchJson<any[]>('/marketplace/products'),
  dashboardMetrics: () => fetchJson<any>('/dashboard/metrics'),
  dashboardTimeseries: () => fetchJson<any>('/dashboard/timeseries?hours=24&bucket_minutes=60'),
  dashboardByVertical: () => fetchJson<any>('/dashboard/by-vertical'),
  connectors: () => fetchJson<any>('/connectors'),
  plans: () => fetchJson<any>('/plans'),
  schemas: () => fetchJson<any>('/schemas'),
  pipeline: () => fetchJson<any>('/pipeline'),

  // Phase 5.1 — self-serve billing, usage analytics, plan upgrades
  changePlan: (api_key: string, plan: string) => fetchJson<any>('/tenants/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key, plan }) }),
  billingInvoice: (apiKey: string) => fetchJson<any>(`/billing/invoice?api_key=${encodeURIComponent(apiKey)}`),
  usage: (apiKey: string) => fetchJson<any>(`/usage?api_key=${encodeURIComponent(apiKey)}`),
  usageAnalytics: (apiKey: string, days = 30) => fetchJson<any>(`/usage/analytics?api_key=${encodeURIComponent(apiKey)}&days=${days}`),
  // Phase 5.5 — API rate-limit dashboard
  rateLimits: () => fetchJson<any>('/ratelimits'),
  rateLimitMe: (apiKey: string) => fetchJson<any>(`/ratelimits/me?api_key=${encodeURIComponent(apiKey)}`),

  // Phase 5.2 — vertical plug-in framework
  verticals: () => fetchJson<any>('/verticals'),
  registerVertical: (body: object) => fetchJson<any>('/verticals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),

  // Phase 5.3 — trading backtesting, risk, broker
  tradingRisk: () => fetchJson<any>('/trading/risk'),
  updateTradingRisk: (body: object) => fetchJson<any>('/trading/risk', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  tradingBacktest: (body: object) => fetchJson<any>('/trading/backtest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  tradingPositions: () => fetchJson<any>('/trading/positions'),
  brokerOrder: (body: object) => fetchJson<any>('/trading/broker/order', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),

  // Phase 5.4 — marketplace datasets + revenue share
  datasets: () => fetchJson<any>('/marketplace/datasets'),
  publishDataset: (body: object) => fetchJson<any>('/marketplace/datasets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  purchaseDataset: (id: string, body: object) => fetchJson<any>(`/marketplace/datasets/${id}/purchase`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  datasetRevenue: (id: string) => fetchJson<any>(`/marketplace/datasets/${id}/revenue`),
  logs: (name: string, lines = 80, container?: string) =>
    fetchJson<{ name: string; source?: string; path?: string; container?: string; lines: string[]; running: boolean }>(
      `/logs/${name}?lines=${lines}${container ? `&source=docker` : ''}`,
    ),
}
