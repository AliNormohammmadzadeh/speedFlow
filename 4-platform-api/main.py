"""Multi-tenant subscription Platform API — FastAPI async gateway."""

from __future__ import annotations

import json
import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as aioredis
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from starlette.responses import Response

import auth as auth_mod
from middleware import TenantQuotaMiddleware, enforce_daily_quota, get_daily_usage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Prometheus metrics (scraped at /metrics) ---
TENANTS_CREATED = Counter("speedflow_tenants_created_total", "Tenants created", ["plan"])
SCRAPES_SUBMITTED = Counter("speedflow_scrapes_submitted_total", "Scrape jobs submitted", ["plan"])
SCRAPE_ERRORS = Counter("speedflow_scrape_errors_total", "Scrape submission errors")

DATABASE_URL = (
    f"postgresql://{os.environ.get('POSTGRES_USER', 'admin')}:"
    f"{os.environ.get('POSTGRES_PASSWORD', 'adminpassword')}@"
    f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/"
    f"{os.environ.get('POSTGRES_DB', 'platform_db')}"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(bind=engine)
_redis: aioredis.Redis | None = None


def load_plans() -> dict:
    path = os.environ.get("PLANS_CONFIG", "/app/config/subscriptions/plans.yaml")
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("plans", {})
    return {}


_plans: dict = load_plans()


def provision_tenant_topic(tenant_id: str) -> str | None:
    """Create the dedicated raw topic + register its Avro schema for a tenant.

    Best-effort: tenant creation must not fail if Kafka/Schema Registry are down.
    Returns the topic name on success, else None.
    """
    topic = f"raw_stream_{tenant_id}"
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    sr_url = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry:8081").rstrip("/")
    created = False
    try:
        from kafka.admin import KafkaAdminClient, NewTopic
        from kafka.errors import TopicAlreadyExistsError

        admin = KafkaAdminClient(bootstrap_servers=bootstrap.split(","), request_timeout_ms=8000)
        try:
            admin.create_topics([NewTopic(name=topic, num_partitions=3, replication_factor=1)])
            created = True
        except TopicAlreadyExistsError:
            created = True
        finally:
            admin.close()
    except Exception as exc:
        logger.warning("tenant topic creation failed for %s: %s", topic, exc)
        return None

    # Register the raw_event schema under the tenant topic's subject by copying
    # the canonical raw_stream-value schema (topic-name subject strategy).
    try:
        with httpx.Client(timeout=8.0) as client:
            latest = client.get(f"{sr_url}/subjects/raw_stream-value/versions/latest")
            if latest.status_code == 200:
                schema_str = latest.json()["schema"]
                client.post(
                    f"{sr_url}/subjects/{topic}-value/versions",
                    headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
                    json={"schema": schema_str},
                )
    except Exception as exc:
        logger.warning("tenant schema registration failed for %s: %s", topic, exc)

    return topic if created else None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
    return _redis


class TenantCreate(BaseModel):
    name: str
    plan: str = "starter"
    email: str | None = None
    role: str = "admin"
    region: str = "us"


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    plan: str
    api_key: str
    kafka_topic_prefix: str
    features: dict[str, Any]
    region: str = "us"


# Data residency (4.10): allowed home regions + their Kafka cluster endpoints.
ALLOWED_REGIONS = [r.strip() for r in os.environ.get("ALLOWED_REGIONS", "us,eu,apac").split(",") if r.strip()]
REGION_CLUSTERS = {
    "us": os.environ.get("KAFKA_US", "kafka-us-broker:9094"),
    "eu": os.environ.get("KAFKA_EU", "kafka-eu-broker:9094"),
    "apac": os.environ.get("KAFKA_APAC", "kafka-apac-broker:9094"),
}


class UsageResponse(BaseModel):
    tenant_id: str
    plan: str
    scrape_requests_used: int
    scrape_requests_limit: int
    scrape_requests_remaining: int


class ScrapeRequest(BaseModel):
    requirement: str = Field(..., description="Natural language description of data to scrape")
    url: str | None = None
    vertical: str | None = None
    max_pages: int | None = None


class ScrapeJobResponse(BaseModel):
    job_id: str
    tenant_id: str
    status: str
    pages_crawled: int = 0
    progress_pct: int = 0
    error_message: str | None = None
    plan: dict[str, Any] | None = None


def resolve_tenant(db: Session, api_key: str | None) -> dict:
    if not api_key:
        raise HTTPException(401, "Missing X-API-Key header")
    row = db.execute(
        text("SELECT * FROM tenants WHERE api_key = :key AND active = true"),
        {"key": api_key},
    ).mappings().first()
    if not row:
        raise HTTPException(401, "Invalid API key")
    return dict(row)


# Per-unit cost estimates (USD) for metering, mirrors config/finops/budgets.yaml.
SCRAPE_UNIT_COST = float(os.environ.get("SCRAPE_UNIT_COST_USD", "0.01"))


def record_usage(tenant_id: str, category: str, units: float, unit_cost: float, meta: dict | None = None) -> None:
    """Meter resource usage into usage_records for billing + FinOps."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO usage_records (tenant_id, category, units, unit_cost_usd, cost_usd, meta) "
                    "VALUES (:tid, :cat, :units, :uc, :cost, CAST(:meta AS JSONB))"
                ),
                {"tid": tenant_id, "cat": category, "units": units, "uc": unit_cost,
                 "cost": round(units * unit_cost, 6), "meta": json.dumps(meta or {})},
            )
    except Exception as exc:
        logger.warning("usage metering failed: %s", exc)


def resolve_tenant_by_id(db: Session, tenant_id: str) -> dict:
    row = db.execute(
        text("SELECT * FROM tenants WHERE tenant_id = :tid AND active = true"),
        {"tid": tenant_id},
    ).mappings().first()
    if not row:
        raise HTTPException(401, "Unknown or inactive tenant")
    return dict(row)


def enforce_plan_limits(tenant: dict, scrape_req: ScrapeRequest) -> dict:
    plan = _plans.get(tenant["plan"], _plans.get("starter", {}))
    limits = plan.get("limits", {})
    if scrape_req.max_pages and scrape_req.max_pages > limits.get("max_pages_per_job", 20):
        scrape_req.max_pages = limits.get("max_pages_per_job", 20)
    return plan


def _merge_job_row(row: dict, live: dict | None = None) -> ScrapeJobResponse:
    data = dict(row)
    live = live or {}
    return ScrapeJobResponse(
        job_id=data["job_id"],
        tenant_id=data["tenant_id"],
        status=live.get("status") or data.get("status", "unknown"),
        pages_crawled=int(live.get("pages_crawled") or data.get("pages_crawled") or 0),
        progress_pct=int(live.get("progress_pct") or data.get("progress_pct") or 0),
        error_message=live.get("error_message") or data.get("error_message"),
        plan=json.loads(data["config"]) if data.get("config") else None,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _plans
    _plans = load_plans()
    # Idempotent migrations for Phase 4 columns (role, billing, residency).
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'admin'"))
            conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS region VARCHAR(32) DEFAULT 'us'"))
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS usage_records ("
                "id SERIAL PRIMARY KEY, tenant_id VARCHAR(32) NOT NULL, category VARCHAR(32) NOT NULL, "
                "units DOUBLE PRECISION DEFAULT 1, unit_cost_usd DOUBLE PRECISION DEFAULT 0, "
                "cost_usd DOUBLE PRECISION DEFAULT 0, meta JSONB DEFAULT '{}', recorded_at TIMESTAMPTZ DEFAULT NOW())"
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_tenant ON usage_records(tenant_id, recorded_at DESC)"))
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS invoices ("
                "id SERIAL PRIMARY KEY, tenant_id VARCHAR(32) NOT NULL, period VARCHAR(7) NOT NULL, "
                "amount_usd DOUBLE PRECISION NOT NULL, breakdown JSONB, status VARCHAR(20) DEFAULT 'draft', "
                "created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE (tenant_id, period))"
            ))
    except Exception as exc:
        logger.warning("startup migration skipped: %s", exc)
    logger.info("Platform API started with %d subscription plans", len(_plans))
    yield
    if _redis:
        await _redis.close()


app = FastAPI(
    title="SpeedFlow Platform API",
    description="Multi-tenant subscription gateway for AI-driven scraping and data pipelines",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    TenantQuotaMiddleware,
    get_plans=lambda: _plans,
    get_redis=get_redis,
    resolve_tenant_fn=resolve_tenant,
    get_db_fn=get_db,
    resolve_tenant_by_id_fn=resolve_tenant_by_id,
)

@app.get("/metrics")
def metrics():
    # Prometheus scrape endpoint (default process + custom counters above).
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "platform-api", "avro": os.environ.get("USE_AVRO", "true")}


@app.post("/tenants", response_model=TenantResponse)
def create_tenant(req: TenantCreate, db: Session = Depends(get_db)):
    if req.plan not in _plans:
        raise HTTPException(400, f"Unknown plan: {req.plan}. Available: {list(_plans.keys())}")
    # Data residency enforcement: reject tenants for non-approved regions.
    if req.region not in ALLOWED_REGIONS:
        raise HTTPException(400, f"Region '{req.region}' not permitted. Allowed: {ALLOWED_REGIONS}")

    tenant_id = str(uuid.uuid4())[:12]
    api_key = f"sf_{secrets.token_urlsafe(24)}"
    topic_prefix = f"tenant_{tenant_id}"

    db.execute(
        text("""
            INSERT INTO tenants (tenant_id, name, email, plan, api_key, kafka_topic_prefix, active, role, region)
            VALUES (:tid, :name, :email, :plan, :key, :prefix, true, :role, :region)
        """),
        {"tid": tenant_id, "name": req.name, "email": req.email, "plan": req.plan, "key": api_key,
         "prefix": topic_prefix, "role": req.role, "region": req.region},
    )
    db.commit()

    plan = _plans[req.plan]
    features = plan.get("features", {})
    TENANTS_CREATED.labels(plan=req.plan).inc()

    # Provision a dedicated per-tenant Kafka topic + schema for Pro/Enterprise.
    if features.get("dedicated_kafka_topic"):
        provisioned = provision_tenant_topic(tenant_id)
        if provisioned:
            logger.info("Provisioned dedicated topic %s for tenant %s", provisioned, tenant_id)

    return TenantResponse(
        tenant_id=tenant_id,
        name=req.name,
        plan=req.plan,
        api_key=api_key,
        kafka_topic_prefix=topic_prefix,
        features=features,
        region=req.region,
    )


@app.get("/residency")
def residency():
    """Data-residency policy: allowed regions and their Kafka cluster endpoints."""
    return {
        "allowed_regions": ALLOWED_REGIONS,
        "region_clusters": {r: REGION_CLUSTERS.get(r) for r in ALLOWED_REGIONS},
    }


class TokenRequest(BaseModel):
    api_key: str


@app.post("/auth/token")
def issue_token(req: TokenRequest, db: Session = Depends(get_db)):
    """OAuth2-style token exchange: trade a tenant API key for a short-lived JWT."""
    tenant = resolve_tenant(db, req.api_key)
    role = tenant.get("role") or "admin"
    token = auth_mod.issue_token(tenant["tenant_id"], role, tenant["plan"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": auth_mod.JWT_TTL_SECONDS,
        "role": role,
        "permissions": auth_mod.permissions_for(role),
    }


def require_permission(permission: str):
    """FastAPI dependency enforcing an RBAC permission from the request principal."""

    def _dep(request: Request):
        perms = getattr(request.state, "permissions", [])
        if not auth_mod.has_permission(perms, permission):
            raise HTTPException(403, f"Missing required permission: {permission}")
        return True

    return _dep


@app.get("/admin/tenants")
def admin_list_tenants(
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(require_permission("deploy")),
):
    """Admin/operator-only tenant listing (RBAC-gated; analysts are denied)."""
    rows = db.execute(
        text("SELECT tenant_id, name, plan, role, region, active FROM tenants ORDER BY created_at DESC LIMIT 100")
    ).mappings().all()
    return {"count": len(rows), "tenants": [dict(r) for r in rows]}


@app.get("/billing/invoice")
def billing_invoice(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Generate the current-month invoice from metered usage + plan base fee."""
    tenant = getattr(request.state, "tenant", None) or resolve_tenant(db, x_api_key)
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    plan = _plans.get(tenant["plan"], {})
    base_fee = float(plan.get("price_usd_monthly", plan.get("price_usd", 0)) or 0)

    rows = db.execute(
        text(
            "SELECT category, SUM(units) AS units, SUM(cost_usd) AS cost FROM usage_records "
            "WHERE tenant_id = :tid AND to_char(recorded_at, 'YYYY-MM') = :period GROUP BY category"
        ),
        {"tid": tenant["tenant_id"], "period": period},
    ).mappings().all()

    usage_breakdown = {r["category"]: {"units": float(r["units"]), "cost_usd": round(float(r["cost"]), 4)} for r in rows}
    usage_total = sum(v["cost_usd"] for v in usage_breakdown.values())
    total = round(base_fee + usage_total, 2)
    breakdown = {"base_fee_usd": base_fee, "usage": usage_breakdown, "usage_total_usd": round(usage_total, 4)}

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO invoices (tenant_id, period, amount_usd, breakdown, status) "
                    "VALUES (:tid, :period, :amt, CAST(:bd AS JSONB), 'draft') "
                    "ON CONFLICT (tenant_id, period) DO UPDATE SET amount_usd = EXCLUDED.amount_usd, "
                    "breakdown = EXCLUDED.breakdown"
                ),
                {"tid": tenant["tenant_id"], "period": period, "amt": total, "bd": json.dumps(breakdown)},
            )
    except Exception as exc:
        logger.warning("invoice upsert failed: %s", exc)

    return {"tenant_id": tenant["tenant_id"], "period": period, "amount_usd": total, "breakdown": breakdown}


@app.get("/tenants/me", response_model=TenantResponse)
def get_current_tenant(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    tenant = resolve_tenant(db, x_api_key)
    plan = _plans.get(tenant["plan"], {})
    return TenantResponse(
        tenant_id=tenant["tenant_id"],
        name=tenant["name"],
        plan=tenant["plan"],
        api_key=tenant["api_key"],
        kafka_topic_prefix=tenant["kafka_topic_prefix"],
        features=plan.get("features", {}),
        region=tenant.get("region", "us"),
    )


@app.get("/usage", response_model=UsageResponse)
async def tenant_usage(
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    tenant = resolve_tenant(db, x_api_key)
    plan = _plans.get(tenant["plan"], {})
    limit = plan.get("limits", {}).get("scrape_requests_per_day", 50)
    usage = await get_daily_usage(redis, tenant["tenant_id"])
    used = usage["scrape_requests_used"]
    return UsageResponse(
        tenant_id=tenant["tenant_id"],
        plan=tenant["plan"],
        scrape_requests_used=used,
        scrape_requests_limit=limit,
        scrape_requests_remaining=max(0, limit - used),
    )


@app.post("/scrape", response_model=ScrapeJobResponse)
async def request_scrape(
    req: ScrapeRequest,
    request: Request,
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    # Accept either the middleware-resolved principal (Bearer JWT or API key) or
    # a direct X-API-Key on the request.
    tenant = getattr(request.state, "tenant", None) or resolve_tenant(db, x_api_key)
    plan = enforce_plan_limits(tenant, req)
    limits = plan.get("limits", {})
    features = plan.get("features", {})

    await enforce_daily_quota(redis, tenant["tenant_id"], limits.get("scrape_requests_per_day", 50))

    orchestrator_url = os.environ.get("AI_ORCHESTRATOR_URL", "http://ai-orchestrator:8000")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{orchestrator_url}/scrape/plan",
            json={
                "requirement": req.requirement,
                "tenant_id": tenant["tenant_id"],
                "hints": {
                    "url": req.url,
                    "vertical": req.vertical,
                    "max_pages": req.max_pages or limits.get("max_pages_per_job", 20),
                },
                "plan_limits": limits,
                "plan_features": features,
            },
        )
        if resp.status_code != 200:
            await redis.decr(f"tenant:{tenant['tenant_id']}:scrape_count:{datetime.now(timezone.utc).strftime('%Y%m%d')}")
            SCRAPE_ERRORS.inc()
            raise HTTPException(502, f"Scrape planner failed: {resp.text}")
        result = resp.json()
    SCRAPES_SUBMITTED.labels(plan=tenant["plan"]).inc()
    # Meter scrape usage for billing + FinOps (units = requested pages).
    pages = req.max_pages or limits.get("max_pages_per_job", 20)
    record_usage(tenant["tenant_id"], "scrape", float(pages), SCRAPE_UNIT_COST, {"job_id": result.get("job_id")})

    job_id = result.get("job_id", "unknown")
    db.execute(
        text("""
            INSERT INTO scrape_jobs (job_id, tenant_id, requirement, status, config, progress_pct)
            VALUES (:jid, :tid, :req, :status, :config, 0)
        """),
        {
            "jid": job_id,
            "tid": tenant["tenant_id"],
            "req": req.requirement,
            "status": result.get("status", "queued"),
            "config": json.dumps(result.get("plan", {})),
        },
    )
    db.commit()

    return ScrapeJobResponse(
        job_id=job_id,
        tenant_id=tenant["tenant_id"],
        status=result.get("status", "queued"),
        progress_pct=0,
        plan=result.get("plan"),
    )


@app.get("/scrape", response_model=list[ScrapeJobResponse])
async def list_scrape_jobs(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    limit: int = 20,
):
    tenant = resolve_tenant(db, x_api_key)
    rows = db.execute(
        text("""
            SELECT * FROM scrape_jobs WHERE tenant_id = :tid
            ORDER BY created_at DESC LIMIT :lim
        """),
        {"tid": tenant["tenant_id"], "lim": limit},
    ).mappings().all()
    return [_merge_job_row(dict(r)) for r in rows]


@app.get("/scrape/{job_id}", response_model=ScrapeJobResponse)
async def get_scrape_job(
    job_id: str,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    tenant = resolve_tenant(db, x_api_key)
    row = db.execute(
        text("SELECT * FROM scrape_jobs WHERE job_id = :jid AND tenant_id = :tid"),
        {"jid": job_id, "tid": tenant["tenant_id"]},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Job not found")

    live = {}
    orchestrator_url = os.environ.get("AI_ORCHESTRATOR_URL", "http://ai-orchestrator:8000")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{orchestrator_url}/scrape/jobs/{job_id}")
            if resp.status_code == 200:
                live = resp.json()
    except Exception:
        pass

    return _merge_job_row(dict(row), live)


@app.get("/features")
def list_plans():
    return {"plans": _plans}
