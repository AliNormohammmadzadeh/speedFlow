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
  logs: (name: string, lines = 80, container?: string) =>
    fetchJson<{ name: string; source?: string; path?: string; container?: string; lines: string[]; running: boolean }>(
      `/logs/${name}?lines=${lines}${container ? `&source=docker` : ''}`,
    ),
}
