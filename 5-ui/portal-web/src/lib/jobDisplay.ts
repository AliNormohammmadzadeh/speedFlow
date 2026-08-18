/** Generic helpers to turn scrape job / event payloads into labeled UI fields. */

export type DisplayField = { label: string; value: string; mono?: boolean }

const LABELS: Record<string, string> = {
  job_id: 'Job ID',
  tenant_id: 'Tenant ID',
  tenant_name: 'Tenant',
  requirement: 'Requirement',
  status: 'Status',
  pages_crawled: 'Pages crawled',
  progress_pct: 'Progress',
  error_message: 'Error',
  created_at: 'Created',
  updated_at: 'Updated',
  plan: 'Plan',
  event_id: 'Event ID',
  event_type: 'Event type',
  source_id: 'Source ID',
  vertical: 'Vertical',
  url: 'URL',
  _page_url: 'Page URL',
  _content_type: 'Content type',
  processing_strategy: 'Processing',
  confidence: 'Confidence',
  timestamp: 'Event time',
  processed_at: 'Processed at',
  max_pages: 'Max pages',
  max_depth: 'Max depth',
  type: 'Scraper type',
}

const SKIP_KEYS = new Set(['payload', 'original', 'features', 'predictions', 'config', 'id'])

export function humanizeKey(key: string): string {
  if (LABELS[key]) return LABELS[key]
  return key
    .replace(/^_/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') return String(value)
  if (Array.isArray(value)) {
    if (!value.length) return '—'
    return value.map(v => (typeof v === 'object' ? JSON.stringify(v) : String(v))).join(', ')
  }
  if (typeof value === 'object') return JSON.stringify(value)
  const s = String(value).trim()
  return s || '—'
}

export function extractDisplayFields(
  obj: Record<string, unknown> | null | undefined,
  opts: { maxDepth?: number; depth?: number } = {},
): DisplayField[] {
  const maxDepth = opts.maxDepth ?? 2
  const depth = opts.depth ?? 0
  if (!obj || depth > maxDepth) return []

  const fields: DisplayField[] = []
  const monoKeys = new Set(['job_id', 'tenant_id', 'event_id', 'source_id', 'url', '_page_url'])

  for (const [key, value] of Object.entries(obj)) {
    if (SKIP_KEYS.has(key)) continue
    if (key.startsWith('_') && key !== '_page_url' && key !== '_content_type') continue
    if (value === null || value === undefined || value === '') continue

    if (typeof value === 'object' && !Array.isArray(value)) {
      if (depth < maxDepth) {
        fields.push(...extractDisplayFields(value as Record<string, unknown>, { maxDepth, depth: depth + 1 }))
      }
      continue
    }

    fields.push({
      label: humanizeKey(key),
      value: formatValue(value),
      mono: monoKeys.has(key) || key.endsWith('_id') || key === 'url',
    })
  }

  return fields
}

export function jobStatusBadge(status?: string): 'up' | 'down' | 'degraded' {
  if (status === 'completed') return 'up'
  if (status === 'failed') return 'down'
  return 'degraded'
}

/** Treat completed jobs with zero pages as failed (legacy rows + clearer UI). */
export function resolveJobStatus(job: {
  status?: string | null
  pages_crawled?: number | null
  error_message?: string | null
}): { status: string; badge: 'up' | 'down' | 'degraded'; failed: boolean; noData: boolean } {
  const pages = job.pages_crawled ?? 0
  const raw = (job.status || 'unknown').toLowerCase()
  const noData = raw === 'completed' && pages === 0
  const failed = raw === 'failed' || noData
  const status = noData ? 'failed' : raw
  return {
    status,
    badge: failed ? 'down' : raw === 'completed' ? 'up' : 'degraded',
    failed,
    noData,
  }
}

export function jobFailureMessage(job: {
  status?: string | null
  pages_crawled?: number | null
  error_message?: string | null
}): string | null {
  const resolved = resolveJobStatus(job)
  if (job.error_message) return job.error_message
  if (resolved.noData) {
    return 'No pages were crawled — target may be blocked, unreachable, or returned no content.'
  }
  if (resolved.failed) return job.error_message || 'Job failed'
  return null
}

export function pipelineStepStatus(status: string): 'up' | 'down' | 'degraded' {
  if (status === 'done') return 'up'
  if (status === 'failed') return 'down'
  if (status === 'active') return 'degraded'
  return 'degraded'
}

export function formatTimestamp(ms?: number | null): string {
  if (!ms) return '—'
  return new Date(ms).toLocaleString()
}

export function formatIso(iso?: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

/** Short human-readable label for page titles (word-safe truncate). */
export function summarizeRequirement(requirement?: string | null, maxLen = 96): string {
  if (!requirement?.trim()) return 'Scrape job'
  const text = requirement.trim().replace(/\s+/g, ' ')
  if (text.length <= maxLen) return text
  const cut = text.slice(0, maxLen)
  const lastSpace = cut.lastIndexOf(' ')
  return (lastSpace > 40 ? cut.slice(0, lastSpace) : cut).trim() + '…'
}

/** Pull http(s) URLs from free-form requirement text. */
export function extractUrlsFromText(text?: string | null): string[] {
  if (!text) return []
  const matches = text.match(/https?:\/\/[^\s)\]"']+/gi) || []
  return [...new Set(matches)]
}
