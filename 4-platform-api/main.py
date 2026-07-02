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


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    plan: str
    api_key: str
    kafka_topic_prefix: str
    features: dict[str, Any]


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

    tenant_id = str(uuid.uuid4())[:12]
    api_key = f"sf_{secrets.token_urlsafe(24)}"
    topic_prefix = f"tenant_{tenant_id}"

    db.execute(
        text("""
            INSERT INTO tenants (tenant_id, name, email, plan, api_key, kafka_topic_prefix, active)
            VALUES (:tid, :name, :email, :plan, :key, :prefix, true)
        """),
        {"tid": tenant_id, "name": req.name, "email": req.email, "plan": req.plan, "key": api_key, "prefix": topic_prefix},
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
    )


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
    db: Session = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    tenant = resolve_tenant(db, x_api_key)
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
