"""SpeedFlow Portal API — aggregates all platform services for the UI."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, text

DATABASE_URL = (
    f"postgresql://{os.environ.get('POSTGRES_USER', 'admin')}:"
    f"{os.environ.get('POSTGRES_PASSWORD', 'adminpassword')}@"
    f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/"
    f"{os.environ.get('POSTGRES_DB', 'platform_db')}"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
    return _redis

SERVICES = {
    "platform_api": os.environ.get("PLATFORM_API_URL", "http://platform-api:8020"),
    "orchestrator": os.environ.get("AI_ORCHESTRATOR_URL", "http://ai-orchestrator:8000"),
    "aggregator": os.environ.get("AGGREGATOR_URL", "http://app-aggregator:8010"),
    "trading_bot": os.environ.get("TRADING_BOT_URL", "http://app-trading-bot:8011"),
    "auditing": os.environ.get("AUDITING_URL", "http://app-auditing:8012"),
    "dashboard": os.environ.get("DASHBOARD_URL", "http://app-dashboard:8013"),
    "marketplace": os.environ.get("MARKETPLACE_URL", "http://app-marketplace:8014"),
    "ml_service": os.environ.get("ML_SERVICE_URL", "http://platform-ml-service:8090"),
    "schema_registry": os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry:8081"),
    "kafka_connect": os.environ.get("KAFKA_CONNECT_URL", "http://platform-kafka-connect:8083"),
    "elasticsearch": os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200"),
    "flink": os.environ.get("FLINK_URL", "http://flink-jobmanager:8081"),
}


class OrchestrateRequest(BaseModel):
    business_goals: list[str] = ["maximize_revenue"]
    run_bridges: bool = True


class TenantCreate(BaseModel):
    name: str
    plan: str = "pro"
    email: str | None = None


class ScrapeRequest(BaseModel):
    requirement: str
    api_key: str
    max_pages: int | None = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="SpeedFlow Portal API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def probe(url: str, path: str = "/health") -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get(f"{url}{path}")
            return {"status": "up" if r.status_code < 400 else "degraded", "code": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else {}}
    except Exception as exc:
        return {"status": "down", "error": str(exc)}


def _serialize_row(row) -> dict:
    data = dict(row)
    for key, val in data.items():
        if hasattr(val, "isoformat"):
            data[key] = val.isoformat()
    return data


@app.get("/api/overview")
async def overview():
    paths = {}
    for name, base in SERVICES.items():
        path = "/health"
        if name == "schema_registry":
            path = "/subjects"
        elif name == "elasticsearch":
            path = "/_cluster/health"
        elif name == "kafka_connect":
            path = "/connectors"
        elif name == "flink":
            path = "/overview"
        paths[name] = (base, path)

    results = await asyncio.gather(*(probe(base, path) for base, path in paths.values()))
    checks = dict(zip(paths.keys(), results))

    up = sum(1 for v in checks.values() if v.get("status") == "up")
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services_up": up,
        "services_total": len(checks),
        "services": checks,
        "pipeline": {
            "ingestion": ["scrapers", "crawlee", "airflow"],
            "messaging": ["kafka", "schema_registry"],
            "compute": ["stream_processor", "flink", "ml_service"],
            "storage": ["postgres", "elasticsearch", "kafka_connect"],
            "intelligence": ["orchestrator", "agents"],
            "serving": ["aggregator", "trading_bot", "dashboard", "marketplace", "auditing"],
        },
    }


@app.get("/api/scrape-jobs")
def list_scrape_jobs(limit: int = 30):
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT sj.*, t.name AS tenant_name, t.plan
                    FROM scrape_jobs sj
                    LEFT JOIN tenants t ON t.tenant_id = sj.tenant_id
                    ORDER BY sj.created_at DESC LIMIT :lim
                """),
                {"lim": limit},
            ).mappings().all()
        return [_serialize_row(r) for r in rows]
    except Exception:
        return []


@app.get("/api/scrape-jobs/{job_id}")
def get_scrape_job(job_id: str):
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT sj.*, t.name AS tenant_name, t.plan
                    FROM scrape_jobs sj
                    LEFT JOIN tenants t ON t.tenant_id = sj.tenant_id
                    WHERE sj.job_id = :jid
                """),
                {"jid": job_id},
            ).mappings().first()
        if not row:
            raise HTTPException(404, f"Scrape job not found: {job_id}")
        data = _serialize_row(row)
        config = data.get("config")
        if isinstance(config, str):
            try:
                import json as _json
                data["config"] = _json.loads(config)
            except Exception:
                data["config"] = {}
        elif config is None:
            data["config"] = {}
        return data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/scrape-jobs/{job_id}/events")
def scrape_job_events(job_id: str, limit: int = 20):
    from processed_events import fetch_job_events

    result = fetch_job_events(engine, job_id, limit=limit)
    if not result.get("found"):
        raise HTTPException(404, f"Scrape job not found: {job_id}")
    return result


@app.get("/api/tenants")
def list_tenants():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT tenant_id, name, plan, email, active, created_at FROM tenants ORDER BY created_at DESC")).mappings().all()
        return [_serialize_row(r) for r in rows]
    except Exception:
        return []


@app.post("/api/tenants")
async def create_tenant(req: TenantCreate):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{SERVICES['platform_api']}/tenants", json=req.model_dump())
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Platform API unavailable: {exc}") from exc


@app.post("/api/scrape")
async def submit_scrape(req: ScrapeRequest):
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                f"{SERVICES['platform_api']}/scrape",
                headers={"X-API-Key": req.api_key},
                json={"requirement": req.requirement, "max_pages": req.max_pages},
            )
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Platform API unavailable: {exc}") from exc


@app.post("/api/orchestrate")
async def orchestrate(req: OrchestrateRequest):
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{SERVICES['orchestrator']}/orchestrate", json=req.model_dump())
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Orchestrator unavailable: {exc}") from exc


@app.get("/api/agents")
async def agents():
    names = ["strategy", "discovery", "processing", "config", "scrape_planner"]
    out = []
    async with httpx.AsyncClient(timeout=5) as client:
        for name in names:
            if name == "scrape_planner":
                out.append({"agent": name, "status": "ready"})
                continue
            try:
                r = await client.get(f"{SERVICES['orchestrator']}/agents/{name}/status")
                out.append(r.json() if r.status_code == 200 else {"agent": name, "status": "unknown"})
            except Exception:
                out.append({"agent": name, "status": "down"})
    return out


@app.get("/api/trading/signals")
async def trading_signals():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['trading_bot']}/signals")
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@app.get("/api/trading/stats")
async def trading_stats():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['trading_bot']}/performance")
            data = r.json() if r.status_code == 200 else {}
            return {
                "pnl_usd": data.get("pnl_usd", 0),
                "win_rate": data.get("win_rate", 0),
                "total_signals": data.get("total_trades", 0),
            }
    except Exception:
        return {"pnl_usd": 0, "win_rate": 0, "total_signals": 0}


@app.get("/api/marketplace/products")
async def marketplace_products():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['marketplace']}/products")
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@app.get("/api/dashboard/metrics")
async def dashboard_metrics():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['dashboard']}/metrics/overview")
            return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


@app.get("/api/dashboard/timeseries")
async def dashboard_timeseries(hours: int = 24, bucket_minutes: int = 60, vertical: str = ""):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{SERVICES['dashboard']}/metrics/timeseries",
                params={"hours": hours, "bucket_minutes": bucket_minutes, "vertical": vertical},
            )
            return r.json() if r.status_code == 200 else {"series": []}
    except Exception:
        return {"series": []}


@app.get("/api/dashboard/by-vertical")
async def dashboard_by_vertical():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['dashboard']}/metrics/by-vertical")
            return r.json() if r.status_code == 200 else {"verticals": []}
    except Exception:
        return {"verticals": []}


@app.get("/api/connectors")
async def connectors():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['kafka_connect']}/connectors")
            if r.status_code != 200:
                return {"connectors": [], "status": "down"}
            names = r.json()
            details = []
            for name in names:
                st = await client.get(f"{SERVICES['kafka_connect']}/connectors/{name}/status")
                details.append({"name": name, "status": st.json() if st.status_code == 200 else {}})
            return {"connectors": details}
    except Exception:
        return {"connectors": [], "status": "down"}


@app.get("/api/plans")
async def plans():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['platform_api']}/features")
            return r.json() if r.status_code == 200 else {"plans": {}}
    except Exception:
        return {"plans": {}}


@app.get("/api/schemas")
async def schemas():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['schema_registry']}/subjects")
            return {"subjects": r.json() if r.status_code == 200 else []}
    except Exception:
        return {"subjects": []}


# --- Phase 5.1: self-serve billing, usage analytics, plan upgrades ---
class PlanChange(BaseModel):
    api_key: str
    plan: str


@app.post("/api/tenants/plan")
async def change_plan(req: PlanChange):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{SERVICES['platform_api']}/tenants/plan",
                headers={"X-API-Key": req.api_key},
                json={"plan": req.plan},
            )
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Platform API unavailable: {exc}") from exc


async def _proxy_get(service: str, path: str, api_key: str | None = None, params: dict | None = None):
    headers = {"X-API-Key": api_key} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{SERVICES[service]}{path}", headers=headers, params=params or {})
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"{service} unavailable: {exc}") from exc


@app.get("/api/billing/invoice")
async def billing_invoice(api_key: str):
    return await _proxy_get("platform_api", "/billing/invoice", api_key)


@app.get("/api/usage")
async def tenant_usage(api_key: str):
    return await _proxy_get("platform_api", "/usage", api_key)


@app.get("/api/usage/analytics")
async def usage_analytics(api_key: str, days: int = 30):
    return await _proxy_get("platform_api", "/usage/analytics", api_key, {"days": days})


@app.get("/api/ratelimits/me")
async def ratelimit_me(api_key: str):
    return await _proxy_get("platform_api", "/ratelimits/me", api_key)


# --- Phase 5.5: platform-wide API rate-limit dashboard (DB + Redis) ---
@app.get("/api/ratelimits")
async def ratelimits():
    from datetime import datetime as _dt

    plans: dict = {}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SERVICES['platform_api']}/features")
            if r.status_code == 200:
                plans = r.json().get("plans", {})
    except Exception:
        plans = {}

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT tenant_id, name, plan FROM tenants WHERE active = true ORDER BY created_at DESC LIMIT 200")
            ).mappings().all()
    except Exception:
        return {"count": 0, "throttled": [], "tenants": []}

    today = _dt.now(timezone.utc).strftime("%Y%m%d")
    redis = get_redis()
    tenants = []
    for row in rows:
        limit = plans.get(row["plan"], {}).get("limits", {}).get("scrape_requests_per_day", 50)
        try:
            raw = await redis.get(f"tenant:{row['tenant_id']}:scrape_count:{today}")
            used = int(raw) if raw else 0
        except Exception:
            used = 0
        tenants.append({
            "tenant_id": row["tenant_id"], "name": row["name"], "plan": row["plan"],
            "used": used, "limit": limit, "remaining": max(0, limit - used),
            "utilization_pct": round(100 * used / limit, 1) if limit else 0.0,
        })
    tenants.sort(key=lambda t: t["utilization_pct"], reverse=True)
    return {"count": len(tenants), "throttled": [t for t in tenants if t["remaining"] == 0], "tenants": tenants}


# --- Phase 5.2: vertical plug-in framework ---
class VerticalRegister(BaseModel):
    id: str
    name: str
    description: str = ""
    priority: int = 99
    seed_sources: list[dict] = []
    target_apps: list[str] = []


@app.get("/api/verticals")
async def list_verticals():
    try:
        return await _proxy_get("orchestrator", "/verticals")
    except HTTPException:
        return {"count": 0, "sources": [], "verticals": []}


@app.post("/api/verticals")
async def register_vertical(req: VerticalRegister):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{SERVICES['orchestrator']}/verticals", json=req.model_dump())
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Orchestrator unavailable: {exc}") from exc


# --- Brain: hierarchical planning proxy ---
class BrainRun(BaseModel):
    objective: str
    context: dict = {}
    use_llm: bool = False
    stop_on_failure: bool = False


@app.get("/api/brain/objectives")
async def brain_objectives():
    try:
        return await _proxy_get("orchestrator", "/brain/objectives")
    except HTTPException:
        return {"objectives": []}


@app.post("/api/brain/plan")
async def brain_plan(req: BrainRun):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{SERVICES['orchestrator']}/brain/plan",
                json={"objective": req.objective, "context": req.context, "use_llm": req.use_llm},
            )
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Orchestrator unavailable: {exc}") from exc


@app.post("/api/brain/execute")
async def brain_execute(req: BrainRun):
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{SERVICES['orchestrator']}/brain/execute",
                json={
                    "objective": req.objective,
                    "context": req.context,
                    "use_llm": req.use_llm,
                    "stop_on_failure": req.stop_on_failure,
                },
            )
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Orchestrator unavailable: {exc}") from exc


# --- Phase 5.3: trading bot risk, backtesting, broker ---
@app.get("/api/trading/risk")
async def trading_risk():
    try:
        return await _proxy_get("trading_bot", "/risk")
    except HTTPException:
        return {}


@app.post("/api/trading/risk")
async def update_trading_risk(body: dict):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{SERVICES['trading_bot']}/risk", json=body)
            return r.json() if r.status_code == 200 else {}
    except Exception as exc:
        raise HTTPException(502, f"Trading bot unavailable: {exc}") from exc


@app.post("/api/trading/backtest")
async def trading_backtest(body: dict):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{SERVICES['trading_bot']}/backtest", json=body)
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Trading bot unavailable: {exc}") from exc


@app.get("/api/trading/positions")
async def trading_positions():
    try:
        return await _proxy_get("trading_bot", "/broker/positions")
    except HTTPException:
        return {"provider": "mock", "cash_usd": 0, "positions": [], "recent_orders": []}


@app.post("/api/trading/broker/order")
async def trading_broker_order(body: dict):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{SERVICES['trading_bot']}/broker/order", json=body)
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Trading bot unavailable: {exc}") from exc


# --- Phase 5.4: marketplace tenant-published datasets ---
@app.get("/api/marketplace/datasets")
async def list_datasets(publisher_tenant: str | None = None):
    params = {"publisher_tenant": publisher_tenant} if publisher_tenant else None
    try:
        return await _proxy_get("marketplace", "/datasets", params=params)
    except HTTPException:
        return {"datasets": []}


@app.post("/api/marketplace/datasets")
async def publish_dataset(body: dict):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{SERVICES['marketplace']}/datasets", json=body)
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Marketplace unavailable: {exc}") from exc


@app.post("/api/marketplace/datasets/{dataset_id}/purchase")
async def purchase_dataset(dataset_id: str, body: dict):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{SERVICES['marketplace']}/datasets/{dataset_id}/purchase", json=body)
            if r.status_code >= 400:
                raise HTTPException(r.status_code, r.text)
            return r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Marketplace unavailable: {exc}") from exc


@app.get("/api/marketplace/datasets/{dataset_id}/revenue")
async def dataset_revenue(dataset_id: str):
    return await _proxy_get("marketplace", f"/datasets/{dataset_id}/revenue")


LOG_PATHS = {
    "platform-api": "/tmp/speedflow-platform-api.log",
    "orchestrator": "/tmp/speedflow-orchestrator.log",
    "portal": "/tmp/speedflow-portal.log",
    "crawlee-worker": "/tmp/speedflow-crawlee-worker.log",
    "stream-processor": "/tmp/speedflow-stream-processor.log",
}

CONTAINER_MAP = {
    "platform-api": "platform-api",
    "orchestrator": "ai-orchestrator",
    "portal": "speedflow-portal",
    "crawlee-worker": "platform-crawlee-worker",
    "stream-processor": "platform-stream-processor",
    "scraper-rest": "scraper-rest",
    "scraper-websocket": "scraper-websocket",
    "scraper-selenium": "scraper-selenium",
    "aggregator": "app-aggregator",
    "trading_bot": "app-trading-bot",
    "trading-bot": "app-trading-bot",
    "auditing": "app-auditing",
    "dashboard": "app-dashboard",
    "marketplace": "app-marketplace",
    "ml_service": "platform-ml-service",
    "kafka_connect": "platform-kafka-connect",
    "elasticsearch": "platform-search",
    "flink": "flink-jobmanager",
    "platform-airflow": "platform-airflow",
}

USE_DOCKER_LOGS = os.environ.get("USE_DOCKER_LOGS", "false").lower() in ("1", "true", "yes")
_docker_client = None


def _get_docker_client():
    global _docker_client
    if _docker_client is None:
        import docker
        _docker_client = docker.from_env()
    return _docker_client


def _tail_docker_logs(name: str, lines: int = 80) -> list[str]:
    container_ref = CONTAINER_MAP.get(name, name)
    try:
        client = _get_docker_client()
        try:
            container = client.containers.get(container_ref)
        except Exception:
            matches = client.containers.list(
                filters={"label": f"com.docker.compose.service={container_ref}"}
            )
            if not matches:
                matches = client.containers.list(all=True, filters={"name": container_ref})
            if not matches:
                return [f"(container not found: {container_ref})"]
            container = matches[0]
        raw = container.logs(tail=lines, timestamps=True)
        text = raw.decode("utf-8", errors="replace")
        return [ln.rstrip("\n") for ln in text.splitlines()[-lines:]]
    except Exception as exc:
        return [f"(docker logs unavailable: {exc})"]


def _tail_log(path: str, lines: int = 80) -> list[str]:
    if not os.path.isfile(path):
        return [f"(log file not found: {path})"]
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.readlines()
        return [ln.rstrip("\n") for ln in content[-lines:]]
    except Exception as exc:
        return [f"(failed to read log: {exc})"]


def _pid_running(name: str) -> bool:
    pidfile = f"/tmp/speedflow-pids/{name}.pid"
    if not os.path.isfile(pidfile):
        return False
    try:
        with open(pidfile) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


@app.get("/api/logs/{name}")
def service_logs(name: str, lines: int = 80, source: str = "auto"):
    lines = min(lines, 200)
    path = LOG_PATHS.get(name)
    container = CONTAINER_MAP.get(name)

    if source == "docker" or (source == "auto" and USE_DOCKER_LOGS and container):
        docker_lines = _tail_docker_logs(name, lines)
        if docker_lines and not docker_lines[0].startswith("(container not found"):
            return {
                "name": name,
                "source": "docker",
                "container": CONTAINER_MAP.get(name, name),
                "lines": docker_lines,
                "running": True,
            }

    if path:
        return {
            "name": name,
            "source": "file",
            "path": path,
            "lines": _tail_log(path, lines),
            "running": _pid_running(name),
        }

    if container:
        return {
            "name": name,
            "source": "docker",
            "container": container,
            "lines": _tail_docker_logs(name, lines),
            "running": True,
        }

    raise HTTPException(404, f"Unknown log source: {name}")


@app.get("/api/pipeline")
async def pipeline_status():
    job_summary = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "total": 0}
    recent_jobs: list[dict] = []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT status, COUNT(*) AS cnt FROM scrape_jobs
                    GROUP BY status
                """)
            ).mappings().all()
            for row in rows:
                st = row["status"] or "unknown"
                if st in job_summary:
                    job_summary[st] = row["cnt"]
                job_summary["total"] += row["cnt"]
            recent = conn.execute(
                text("""
                    SELECT job_id, tenant_id, status, pages_crawled, progress_pct, requirement, error_message, created_at
                    FROM scrape_jobs ORDER BY created_at DESC LIMIT 5
                """)
            ).mappings().all()
            recent_jobs = [_serialize_row(r) for r in recent]
    except Exception:
        pass

    host_workers = {
        name: {"running": _pid_running(name), "log_path": path}
        for name, path in LOG_PATHS.items()
        if name in ("crawlee-worker", "stream-processor", "platform-api", "orchestrator", "portal")
    }

    schemas_list: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{SERVICES['schema_registry']}/subjects")
            if r.status_code == 200:
                schemas_list = r.json()
    except Exception:
        pass

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flow": [
            {"step": 1, "name": "Scrape Request", "via": "Platform API :8020"},
            {"step": 2, "name": "AI Scrape Planner", "via": "Orchestrator :8000"},
            {"step": 3, "name": "Crawlee Worker", "via": "Redis queue → crawl"},
            {"step": 4, "name": "raw_stream", "via": "Kafka + Avro"},
            {"step": 5, "name": "Stream Processor", "via": "Stateful compute"},
            {"step": 6, "name": "processed_stream", "via": "Kafka sink / ES"},
        ],
        "topics": ["raw_stream", "processed_stream", "feedback_metrics"],
        "schemas": schemas_list,
        "job_summary": job_summary,
        "recent_jobs": recent_jobs,
        "host_workers": host_workers,
    }


# --- MVP scorecard + live end-to-end proof ------------------------------------
# These power the public landing page and the "MVP Showcase" console page. The
# scorecard reports live readiness; the demo actually exercises the platform
# end-to-end (tenant → AI scrape → Kafka pipeline → Brain verification) so the
# UI can prove the MVP works rather than just claiming it.

MVP_CAPABILITIES = [
    {"key": "brain", "title": "Agentic Brain — hierarchical planning & per-step verification", "layer": "Intelligence"},
    {"key": "ingestion", "title": "Adaptive ingestion — Crawlee workers + REST/WS/Selenium scrapers", "layer": "Ingestion"},
    {"key": "streaming", "title": "Real-time stream compute — Kafka + Avro raw_stream → processed_stream", "layer": "Compute"},
    {"key": "multitenant", "title": "Multi-tenant gateway — plans, API keys, quotas & billing", "layer": "Platform"},
    {"key": "serving", "title": "Serving apps — trading bot, aggregator, marketplace, auditing", "layer": "Serving"},
    {"key": "portal", "title": "Control portal — live health, pipeline canvas & this showcase", "layer": "UI"},
]


class DemoRequest(BaseModel):
    url: str = "https://example.com"
    objective: str = "launch_scrape_pipeline"


@app.get("/api/mvp/status")
async def mvp_status():
    """Live MVP readiness scorecard: service health + real platform metrics."""
    ov = await overview()
    services = ov["services"]

    tenants_count = 0
    completed_jobs = 0
    total_jobs = 0
    try:
        with engine.connect() as conn:
            tenants_count = conn.execute(text("SELECT COUNT(*) FROM tenants")).scalar() or 0
            for row in conn.execute(
                text("SELECT status, COUNT(*) AS cnt FROM scrape_jobs GROUP BY status")
            ).mappings().all():
                total_jobs += row["cnt"]
                if row["status"] == "completed":
                    completed_jobs = row["cnt"]
    except Exception:
        pass

    objectives: list = []
    try:
        objectives = (await _proxy_get("orchestrator", "/brain/objectives")).get("objectives", [])
    except Exception:
        objectives = []

    schema_subjects: list = []
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{SERVICES['schema_registry']}/subjects")
            if r.status_code == 200:
                schema_subjects = r.json()
    except Exception:
        schema_subjects = []

    def up(*keys: str) -> bool:
        return all(services.get(k, {}).get("status") == "up" for k in keys)

    readiness = {
        "brain": bool(objectives) and up("orchestrator"),
        "ingestion": up("platform_api"),
        "streaming": bool(schema_subjects) and up("schema_registry"),
        "multitenant": up("platform_api"),
        "serving": any(up(k) for k in ("trading_bot", "marketplace", "aggregator")),
        "portal": True,
    }
    capabilities = [{**c, "ready": bool(readiness.get(c["key"]))} for c in MVP_CAPABILITIES]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services_up": ov["services_up"],
        "services_total": ov["services_total"],
        "capabilities": capabilities,
        "capabilities_ready": sum(1 for c in capabilities if c["ready"]),
        "capabilities_total": len(capabilities),
        "metrics": {
            "tenants": tenants_count,
            "completed_jobs": completed_jobs,
            "total_jobs": total_jobs,
            "brain_objectives": len(objectives),
            "schemas": len(schema_subjects),
        },
        "objectives": [o.get("objective") for o in objectives],
    }


@app.post("/api/mvp/demo")
async def mvp_demo(req: DemoRequest):
    """Run a live end-to-end proof and stream the per-step results as JSON.

    Steps: provision a starter tenant → submit an AI-planned scrape → wait for
    the Kafka pipeline to complete the job → let the Brain plan/execute/verify
    the pipeline objective. Every step reports pass/fail with real details.
    """
    import time

    steps: list[dict] = []
    result: dict = {"ok": False, "steps": steps}

    def begin(key: str, label: str) -> tuple[dict, float]:
        step = {"key": key, "label": label, "status": "running", "detail": "", "ms": 0}
        steps.append(step)
        return step, time.monotonic()

    def finish(step: dict, t0: float, status: str, detail: str) -> None:
        step["status"] = status
        step["detail"] = detail[:240]
        step["ms"] = int((time.monotonic() - t0) * 1000)

    # 1. Provision a starter tenant (starter → shared raw_stream the host
    #    stream processor consumes, so events reach processed_stream).
    step, t0 = begin("tenant", "Provision starter tenant")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{SERVICES['platform_api']}/tenants",
                json={"name": f"MVP Demo {int(time.time())}", "plan": "starter", "email": "demo@speedflow.local"},
            )
            r.raise_for_status()
            data = r.json()
        api_key, tenant_id = data["api_key"], data["tenant_id"]
        finish(step, t0, "passed", f"tenant {tenant_id[:12]} · plan starter")
    except Exception as exc:
        finish(step, t0, "failed", f"platform-api error: {exc}")
        return result

    # 2. Submit an AI-planned scrape job.
    step, t0 = begin("scrape", "Submit AI-planned scrape job")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{SERVICES['platform_api']}/scrape",
                headers={"X-API-Key": api_key},
                json={"requirement": f"Scrape page titles from {req.url}", "max_pages": 1},
            )
            r.raise_for_status()
            job_id = r.json()["job_id"]
        finish(step, t0, "passed", f"job {job_id[:12]} queued for {req.url}")
    except Exception as exc:
        finish(step, t0, "failed", f"scrape submit failed: {exc}")
        return result

    # 3. Wait for the pipeline (crawlee → raw_stream → stream processor) to
    #    drive the job to completion.
    step, t0 = begin("pipeline", "Crawl → raw_stream → processed_stream")
    status, pages, error_message = "unknown", 0, ""
    for _ in range(40):
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT status, pages_crawled, error_message FROM scrape_jobs WHERE job_id=:j"),
                    {"j": job_id},
                ).mappings().first()
            if row:
                status = row["status"] or "unknown"
                pages = row["pages_crawled"] or 0
                error_message = row.get("error_message") or ""
        except Exception:
            pass
        if status in ("completed", "failed"):
            break
        await asyncio.sleep(1.5)
    if status == "completed" and pages > 0:
        finish(step, t0, "passed", f"job completed · {pages} page(s) crawled & streamed")
    elif status == "completed" and pages == 0:
        finish(
            step,
            t0,
            "failed",
            error_message or "job completed with 0 pages — target blocked or unreachable",
        )
        return result
    elif status == "failed":
        finish(step, t0, "failed", error_message or f"job failed after wait (status={status})")
        return result
    else:
        finish(step, t0, "failed", f"job status={status} after wait — see crawlee-worker logs")
        return result

    # 4. Brain plans, executes and verifies the pipeline objective live.
    step, t0 = begin("brain", f"Brain verifies objective “{req.objective}”")
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                f"{SERVICES['orchestrator']}/brain/execute",
                json={"objective": req.objective},
            )
            r.raise_for_status()
            report = r.json()["report"]
        summ = report["summary"]
        ok = bool(report.get("success")) and summ["failed"] == 0 and summ["checks"] == summ["checks_passed"]
        detail = f"{summ['passed']}/{summ['total']} steps · {summ['checks_passed']}/{summ['checks']} checks verified"
        finish(step, t0, "passed" if ok else "failed", detail)
        if not ok:
            return result
    except Exception as exc:
        finish(step, t0, "failed", f"brain execute failed: {exc}")
        return result

    result["ok"] = True
    return result


static_dir = os.environ.get("PORTAL_STATIC_DIR", "/app/static")
if os.path.isdir(static_dir):
    from fastapi.responses import FileResponse

    # Hashed bundle assets are served directly.
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    # SPA fallback: real files at the web root (icon.svg, manifest.webmanifest,
    # sw.js, ...) are served as-is; every other path returns index.html so
    # client-side routes (e.g. /canvas) work on direct load and refresh.
    # Declared last, so the /api/* routes above always take precedence.
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "API endpoint not found")
        candidate = os.path.join(static_dir, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(static_dir, "index.html"))
