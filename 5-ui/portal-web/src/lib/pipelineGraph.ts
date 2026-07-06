import {
  Bot,
  Cloud,
  Cpu,
  Database,
  Layers,
  LineChart,
  Search,
  Server,
  Store,
  type LucideIcon,
} from 'lucide-react'

export type NodeKind =
  | 'api'
  | 'ai'
  | 'scraper'
  | 'queue'
  | 'compute'
  | 'database'
  | 'search'
  | 'serving'

export type PipelineNodeDef = {
  id: string
  label: string
  subtitle: string
  kind: NodeKind
  icon: LucideIcon
  /** Tailwind gradient stops for the icon chip. */
  accent: string
  /** rgba used for the node's outer glow when active. */
  glow: string
  /** Sparkline metric label + unit shown at the bottom of the card. */
  metric: string
  unit: string
  /** Baseline value the mocked sparkline oscillates around. */
  baseline: number
  /** Key into `overview.services` for live health; omit for host/infra nodes. */
  statusKey?: string
}

export const PIPELINE_NODES: PipelineNodeDef[] = [
  {
    id: 'platform_api',
    label: 'Platform API',
    subtitle: 'Multi-tenant gateway',
    kind: 'api',
    icon: Server,
    accent: 'from-cyan-400 to-blue-500',
    glow: 'rgba(34,211,238,0.55)',
    metric: 'requests',
    unit: 'req/s',
    baseline: 42,
    statusKey: 'platform_api',
  },
  {
    id: 'orchestrator',
    label: 'AI Orchestrator',
    subtitle: 'Agent swarm + planner',
    kind: 'ai',
    icon: Bot,
    accent: 'from-violet-400 to-purple-500',
    glow: 'rgba(167,139,250,0.55)',
    metric: 'plans',
    unit: 'jobs/m',
    baseline: 18,
    statusKey: 'orchestrator',
  },
  {
    id: 'ingest',
    label: 'Crawlee Workers',
    subtitle: 'Ingestion edge',
    kind: 'scraper',
    icon: Cloud,
    accent: 'from-sky-400 to-cyan-500',
    glow: 'rgba(56,189,248,0.55)',
    metric: 'pages',
    unit: 'pg/s',
    baseline: 120,
  },
  {
    id: 'raw_stream',
    label: 'raw_stream',
    subtitle: 'Kafka topic · Avro',
    kind: 'queue',
    icon: Layers,
    accent: 'from-fuchsia-400 to-violet-500',
    glow: 'rgba(217,70,239,0.5)',
    metric: 'events',
    unit: 'ev/s',
    baseline: 210,
    statusKey: 'schema_registry',
  },
  {
    id: 'stream_processor',
    label: 'Stream Processor',
    subtitle: 'Stateful compute',
    kind: 'compute',
    icon: Cpu,
    accent: 'from-pink-400 to-rose-500',
    glow: 'rgba(244,114,182,0.55)',
    metric: 'cpu',
    unit: '%',
    baseline: 63,
  },
  {
    id: 'processed_stream',
    label: 'processed_stream',
    subtitle: 'Kafka topic · Avro',
    kind: 'queue',
    icon: Layers,
    accent: 'from-fuchsia-400 to-violet-500',
    glow: 'rgba(217,70,239,0.5)',
    metric: 'events',
    unit: 'ev/s',
    baseline: 190,
    statusKey: 'schema_registry',
  },
  {
    id: 'postgres',
    label: 'PostgreSQL',
    subtitle: 'processed_events sink',
    kind: 'database',
    icon: Database,
    accent: 'from-emerald-400 to-teal-500',
    glow: 'rgba(52,211,153,0.5)',
    metric: 'writes',
    unit: 'w/s',
    baseline: 95,
  },
  {
    id: 'opensearch',
    label: 'OpenSearch',
    subtitle: 'Search index',
    kind: 'search',
    icon: Search,
    accent: 'from-emerald-400 to-green-500',
    glow: 'rgba(52,211,153,0.5)',
    metric: 'indexed',
    unit: 'doc/s',
    baseline: 88,
    statusKey: 'elasticsearch',
  },
  {
    id: 'trading_bot',
    label: 'Trading Bot',
    subtitle: 'Live buy/sell signals',
    kind: 'serving',
    icon: LineChart,
    accent: 'from-cyan-400 to-emerald-500',
    glow: 'rgba(34,211,238,0.5)',
    metric: 'signals',
    unit: 'sig/m',
    baseline: 26,
    statusKey: 'trading_bot',
  },
  {
    id: 'marketplace',
    label: 'Marketplace',
    subtitle: 'Data products',
    kind: 'serving',
    icon: Store,
    accent: 'from-pink-400 to-fuchsia-500',
    glow: 'rgba(244,114,182,0.5)',
    metric: 'orders',
    unit: 'ord/m',
    baseline: 12,
    statusKey: 'marketplace',
  },
  {
    id: 'dashboard',
    label: 'Meta Dashboard',
    subtitle: 'Analytics & KPIs',
    kind: 'serving',
    icon: LineChart,
    accent: 'from-violet-400 to-indigo-500',
    glow: 'rgba(167,139,250,0.5)',
    metric: 'queries',
    unit: 'q/m',
    baseline: 34,
    statusKey: 'dashboard',
  },
]

export type PipelineEdgeDef = {
  source: string
  target: string
  /** Relative data volume 1..10 — drives edge thickness + particle speed. */
  volume: number
}

export const PIPELINE_EDGES: PipelineEdgeDef[] = [
  { source: 'platform_api', target: 'orchestrator', volume: 2 },
  { source: 'orchestrator', target: 'ingest', volume: 3 },
  { source: 'ingest', target: 'raw_stream', volume: 7 },
  { source: 'raw_stream', target: 'stream_processor', volume: 8 },
  { source: 'stream_processor', target: 'processed_stream', volume: 8 },
  { source: 'processed_stream', target: 'postgres', volume: 6 },
  { source: 'processed_stream', target: 'opensearch', volume: 5 },
  { source: 'processed_stream', target: 'trading_bot', volume: 4 },
  { source: 'processed_stream', target: 'marketplace', volume: 3 },
  { source: 'processed_stream', target: 'dashboard', volume: 3 },
]
