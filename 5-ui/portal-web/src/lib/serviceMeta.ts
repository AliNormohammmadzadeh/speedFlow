export type ServiceMeta = {
  label: string
  description: string
  layer: string
  port?: number
  healthUrl?: string
  logName?: string
  container?: string
  topics?: string[]
}

export const SERVICE_META: Record<string, ServiceMeta> = {
  platform_api: {
    label: 'Platform API',
    description: 'Multi-tenant gateway — tenants, scrape jobs, quotas',
    layer: 'Platform',
    port: 8020,
    healthUrl: 'http://localhost:8020/health',
    logName: 'platform-api',
    container: 'platform-api',
  },
  orchestrator: {
    label: 'AI Orchestrator',
    description: 'Agent swarm + scrape planner → Redis queue',
    layer: 'Intelligence',
    port: 8000,
    healthUrl: 'http://localhost:8000/health',
    logName: 'orchestrator',
    container: 'ai-orchestrator',
  },
  aggregator: {
    label: 'Aggregator',
    description: 'Accommodation search & aggregation API',
    layer: 'Serving',
    port: 8010,
    healthUrl: 'http://localhost:8010/health',
    container: 'app-aggregator',
  },
  trading_bot: {
    label: 'Trading Bot',
    description: 'Live signals from processed stream events',
    layer: 'Serving',
    port: 8011,
    healthUrl: 'http://localhost:8011/health',
    container: 'app-trading-bot',
  },
  auditing: {
    label: 'Auditing',
    description: 'Compliance & audit trail service',
    layer: 'Serving',
    port: 8012,
    healthUrl: 'http://localhost:8012/health',
    container: 'app-auditing',
  },
  dashboard: {
    label: 'Meta Dashboard',
    description: 'Platform metrics & analytics UI',
    layer: 'Serving',
    port: 8013,
    healthUrl: 'http://localhost:8013/health',
    container: 'app-dashboard',
  },
  marketplace: {
    label: 'Marketplace',
    description: 'Data product catalog & licensing',
    layer: 'Serving',
    port: 8014,
    healthUrl: 'http://localhost:8014/health',
    container: 'app-marketplace',
  },
  ml_service: {
    label: 'ML Service',
    description: 'sklearn / CUDA batch inference',
    layer: 'Compute',
    port: 8090,
    healthUrl: 'http://localhost:8090/health',
    container: 'platform-ml-service',
  },
  schema_registry: {
    label: 'Schema Registry',
    description: 'Avro schemas for raw_stream & processed_stream',
    layer: 'Messaging',
    port: 8081,
    healthUrl: 'http://localhost:8081/subjects',
    container: 'platform-schema-registry',
    topics: ['raw_stream-value', 'processed_stream-value'],
  },
  kafka_connect: {
    label: 'Kafka Connect',
    description: 'JDBC + Elasticsearch sinks',
    layer: 'Storage',
    port: 8083,
    healthUrl: 'http://localhost:8083/connectors',
    container: 'platform-kafka-connect',
  },
  elasticsearch: {
    label: 'OpenSearch',
    description: 'Search index for processed events',
    layer: 'Storage',
    port: 9200,
    healthUrl: 'http://localhost:9200/_cluster/health',
    container: 'platform-search',
  },
  flink: {
    label: 'Flink',
    description: 'Stateful stream processing cluster',
    layer: 'Compute',
    port: 8082,
    healthUrl: 'http://localhost:8082/overview',
    container: 'flink-jobmanager',
  },
}

export const HOST_WORKERS: Record<string, ServiceMeta> = {
  'crawlee-worker': {
    label: 'Crawlee Worker',
    description: 'Consumes Redis crawlee:jobs → publishes raw_stream',
    layer: 'Ingestion',
    logName: 'crawlee-worker',
  },
  'stream-processor': {
    label: 'Stream Processor',
    description: 'raw_stream → feature extraction → processed_stream',
    layer: 'Compute',
    logName: 'stream-processor',
    container: 'platform-stream-processor',
  },
}

export const SCRAPER_META: Record<string, ServiceMeta & { type: string }> = {
  'scraper-rest': { label: 'REST Scraper', type: 'rest', description: 'HTTP polling scraper', layer: 'Ingestion', container: 'scraper-rest' },
  'scraper-websocket': { label: 'WebSocket Scraper', type: 'websocket', description: 'Real-time WS feeds', layer: 'Ingestion', container: 'scraper-websocket' },
  'scraper-selenium': { label: 'Selenium + Chrome', type: 'selenium', description: 'Headless browser automation', layer: 'Ingestion', container: 'scraper-selenium' },
  'crawlee-worker': { label: 'Crawlee Workers', type: 'crawlee', description: 'AI-planned crawl jobs', layer: 'Ingestion', logName: 'crawlee-worker', container: 'crawlee-worker' },
  'platform-airflow': { label: 'Airflow', type: 'orchestration', description: 'DAG scheduling & ETL', layer: 'Ingestion', port: 8080, container: 'platform-airflow' },
}

export const PIPELINE_STAGES = [
  {
    id: 'ingestion',
    label: 'Ingestion Edge',
    color: 'from-cyan-500 to-blue-500',
    items: [
      { id: 'scraper-rest', label: 'REST / WS Scrapers' },
      { id: 'crawlee-worker', label: 'Crawlee Workers' },
      { id: 'scraper-selenium', label: 'Selenium / Playwright' },
      { id: 'platform-airflow', label: 'Airflow DAGs' },
    ],
  },
  {
    id: 'messaging',
    label: 'Kafka + Avro',
    color: 'from-violet-500 to-purple-500',
    items: [
      { id: 'topic-raw', label: 'raw_stream', topic: true },
      { id: 'topic-processed', label: 'processed_stream', topic: true },
      { id: 'schema_registry', label: 'Schema Registry' },
    ],
  },
  {
    id: 'compute',
    label: 'Stream Compute',
    color: 'from-fuchsia-500 to-pink-500',
    items: [
      { id: 'stream-processor', label: 'Stream Processor' },
      { id: 'flink', label: 'Flink Cluster' },
      { id: 'ml_service', label: 'ML Service' },
    ],
  },
  {
    id: 'storage',
    label: 'Storage',
    color: 'from-emerald-500 to-teal-500',
    items: [
      { id: 'postgres', label: 'PostgreSQL', port: 5433 },
      { id: 'elasticsearch', label: 'Elasticsearch' },
      { id: 'kafka_connect', label: 'Kafka Connect' },
    ],
  },
]
