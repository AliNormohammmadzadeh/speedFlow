-- SpeedFlow PostgreSQL initialization

CREATE TABLE IF NOT EXISTS processed_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    vertical VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    timestamp BIGINT NOT NULL,
    processed_at BIGINT NOT NULL,
    confidence DOUBLE PRECISION,
    processing_strategy VARCHAR(50),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_processed_events_vertical ON processed_events(vertical);
CREATE INDEX IF NOT EXISTS idx_processed_events_type ON processed_events(event_type);
CREATE INDEX IF NOT EXISTS idx_processed_events_ts ON processed_events(timestamp DESC);

CREATE TABLE IF NOT EXISTS trading_signals (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) REFERENCES processed_events(event_id),
    symbol VARCHAR(50) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    price DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    executed BOOLEAN DEFAULT FALSE,
    pnl_usd DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback_metrics (
    id SERIAL PRIMARY KEY,
    app_name VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_app ON feedback_metrics(app_name, recorded_at DESC);

CREATE TABLE IF NOT EXISTS marketplace_orders (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(100) NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    price_usd DOUBLE PRECISION NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(100) NOT NULL,
    actor VARCHAR(100),
    resource VARCHAR(255),
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Multi-tenant subscription platform
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    plan VARCHAR(50) NOT NULL DEFAULT 'starter',
    api_key VARCHAR(128) UNIQUE NOT NULL,
    kafka_topic_prefix VARCHAR(64) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_api_key ON tenants(api_key);

CREATE TABLE IF NOT EXISTS scrape_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) UNIQUE NOT NULL,
    tenant_id VARCHAR(32) NOT NULL REFERENCES tenants(tenant_id),
    requirement TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'queued',
    config JSONB DEFAULT '{}',
    pages_crawled INT DEFAULT 0,
    progress_pct INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scrape_jobs_tenant ON scrape_jobs(tenant_id, created_at DESC);

ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_processed_events_tenant ON processed_events(tenant_id);
