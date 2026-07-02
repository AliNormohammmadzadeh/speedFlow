"""AI Orchestrator - coordinates multi-agent swarm."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import redis
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from agents.scrape_planner_agent import ScrapePlannerAgent
from agents.config_agent import ConfigAgent
from agents.discovery_agent import DiscoveryAgent
from agents.processing_agent import ProcessingAgent
from agents.strategy_agent import StrategyAgent
from bridges.config_bridge import ConfigBridge
from bridges.processing_bridge import ProcessingBridge
from bridges.scraper_bridge import ScraperBridge
from shared.utils import AgentState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = (
    f"postgresql://{os.environ.get('POSTGRES_USER', 'admin')}:"
    f"{os.environ.get('POSTGRES_PASSWORD', 'adminpassword')}@"
    f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/"
    f"{os.environ.get('POSTGRES_DB', 'platform_db')}"
)
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def persist_feedback(app_name: str, metrics: dict[str, float]) -> int:
    """Store each metric as a row in feedback_metrics; returns rows written."""
    from sqlalchemy import text

    written = 0
    try:
        with get_engine().begin() as conn:
            for name, value in metrics.items():
                try:
                    fval = float(value)
                except (TypeError, ValueError):
                    continue
                conn.execute(
                    text(
                        "INSERT INTO feedback_metrics (app_name, metric_name, metric_value) "
                        "VALUES (:app, :name, :val)"
                    ),
                    {"app": app_name, "name": name, "val": fval},
                )
                written += 1
    except Exception as exc:
        logger.warning("feedback_metrics persistence failed: %s", exc)
    return written


def load_recent_feedback(hours: int = 24) -> list[dict]:
    """Load recent feedback from Postgres, shaped for the Strategy Agent."""
    from sqlalchemy import text

    try:
        with get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT app_name, metric_name, metric_value FROM feedback_metrics "
                    "WHERE recorded_at > NOW() - make_interval(hours => :h) "
                    "ORDER BY recorded_at DESC LIMIT 500"
                ),
                {"h": hours},
            ).mappings().all()
        return [
            {"app_name": r["app_name"], "metric_name": r["metric_name"], "metric_value": r["metric_value"]}
            for r in rows
        ]
    except Exception as exc:
        logger.warning("feedback history load failed: %s", exc)
        return []


scrape_planner = ScrapePlannerAgent()
strategy_agent = StrategyAgent()
discovery_agent = DiscoveryAgent()
processing_agent = ProcessingAgent()
config_agent = ConfigAgent()
scraper_bridge = ScraperBridge()
processing_bridge = ProcessingBridge()
config_bridge = ConfigBridge()


class OrchestrationRequest(BaseModel):
    business_goals: list[str] = ["maximize_revenue"]
    feedback: list[dict] = []
    desired_state: dict = {}
    run_bridges: bool = True


class FeedbackRequest(BaseModel):
    app_name: str
    metrics: dict[str, float]


class OrchestrationResponse(BaseModel):
    cycle_id: str
    state: dict[str, Any]
    bridges_applied: dict[str, Any] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Orchestrator started")
    yield


app = FastAPI(title="SpeedFlow AI Orchestrator", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "agents": ["strategy", "discovery", "processing", "config", "scrape_planner"]}


@app.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(req: OrchestrationRequest, background_tasks: BackgroundTasks):
    """Run full agent cycle: Strategy -> Discovery -> Processing -> Config -> Bridges."""
    import uuid
    cycle_id = str(uuid.uuid4())[:8]
    state = AgentState()

    # Merge persisted feedback history (Postgres) with any inline feedback so the
    # Strategy Agent reacts to accumulated app metrics, not just this request.
    feedback = list(req.feedback) + load_recent_feedback()
    strategy_out = await strategy_agent.run(state, feedback=feedback)
    discovery_out = await discovery_agent.run(state, data_gaps=strategy_out.get("data_gaps"))
    processing_out = await processing_agent.run(state)
    config_out = await config_agent.run(state, desired_state=req.desired_state or None)

    bridges_applied = None
    if req.run_bridges:
        bridges_applied = {
            "scraper_jobs": scraper_bridge.push_targets(discovery_out.get("scraping_targets", [])),
            "processing": processing_bridge.inject_decisions(processing_out.get("processing_decisions", [])),
            "config": config_bridge.deploy(config_out),
        }

    # Publish cycle to feedback topic
    background_tasks.add_task(_publish_cycle, cycle_id, state.to_dict())

    return OrchestrationResponse(cycle_id=cycle_id, state=state.to_dict(), bridges_applied=bridges_applied)


@app.post("/feedback")
async def receive_feedback(req: FeedbackRequest):
    """Receive performance metrics from end-use apps; persist to Postgres history."""
    # Durable history (Postgres) so feedback survives restarts and can be replayed
    # into the Strategy Agent on later orchestration cycles.
    written = persist_feedback(req.app_name, req.metrics)
    # Keep the Redis list too for any low-latency consumers.
    try:
        client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        for name, value in req.metrics.items():
            client.rpush("feedback:metrics", json.dumps({
                "app_name": req.app_name,
                "metric_name": name,
                "metric_value": value,
            }))
    except Exception as exc:
        logger.warning("feedback redis push failed: %s", exc)
    return {"status": "recorded", "app": req.app_name, "metrics_count": len(req.metrics), "persisted": written}


@app.get("/feedback/history")
def feedback_history(hours: int = 24, app_name: str | None = None):
    """Return persisted feedback history from Postgres."""
    from sqlalchemy import text

    query = (
        "SELECT app_name, metric_name, metric_value, recorded_at FROM feedback_metrics "
        "WHERE recorded_at > NOW() - make_interval(hours => :h) "
    )
    params: dict[str, Any] = {"h": hours}
    if app_name:
        query += "AND app_name = :app "
        params["app"] = app_name
    query += "ORDER BY recorded_at DESC LIMIT 500"
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(query), params).mappings().all()
        return {
            "count": len(rows),
            "history": [
                {
                    "app_name": r["app_name"],
                    "metric_name": r["metric_name"],
                    "metric_value": r["metric_value"],
                    "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
                }
                for r in rows
            ],
        }
    except Exception as exc:
        raise HTTPException(503, f"feedback history unavailable: {exc}")


@app.get("/agents/{agent_name}/status")
def agent_status(agent_name: str):
    valid = {"strategy", "discovery", "processing", "config"}
    if agent_name not in valid:
        raise HTTPException(404, f"Unknown agent: {agent_name}")
    return {"agent": agent_name, "status": "ready"}


class ScrapePlanRequest(BaseModel):
    requirement: str
    tenant_id: str | None = None
    hints: dict = {}
    plan_limits: dict = {}
    plan_features: dict = {}


class ScrapePlanResponse(BaseModel):
    job_id: str
    tenant_id: str | None
    status: str
    plan: dict[str, Any]


@app.post("/scrape/plan", response_model=ScrapePlanResponse)
async def plan_and_queue_scrape(req: ScrapePlanRequest):
    """AI selects Crawlee parameters from user requirement and queues the job."""
    plan = await scrape_planner.plan_from_requirement(
        req.requirement,
        tenant_id=req.tenant_id,
        hints=req.hints,
    )

    # Enforce subscription limits
    limits = req.plan_limits or {}
    features = req.plan_features or {}
    plan["max_pages"] = min(plan.get("max_pages", 50), limits.get("max_pages_per_job", 50))
    plan["max_concurrency"] = min(plan.get("max_concurrency", 5), limits.get("max_concurrency", 5))
    if not features.get("proxy", False):
        plan["use_proxy"] = False
    if features.get("proxy_tier"):
        plan["proxy_tier"] = features["proxy_tier"]

    allowed = features.get("scrapers", ["crawlee"])
    if plan.get("crawler_type") == "playwright" and "crawlee_playwright" not in allowed:
        plan["crawler_type"] = "beautifulsoup"

    if features.get("dedicated_kafka_topic") and req.tenant_id:
        plan["kafka_topic"] = f"raw_stream_{req.tenant_id}"

    result = scraper_bridge.push_crawl_job(plan, tenant_id=req.tenant_id)
    return ScrapePlanResponse(
        job_id=result["job_id"],
        tenant_id=req.tenant_id,
        status="queued",
        plan=plan,
    )


@app.get("/scrape/jobs/{job_id}")
def get_scrape_job_status(job_id: str):
    return scraper_bridge.job_status(job_id)


@app.post("/agents/discovery/push-targets")
def push_scraper_targets(targets: list[dict]):
    count = scraper_bridge.push_targets(targets)
    return {"pushed": count, "queue_length": scraper_bridge.queue_length()}


async def _publish_cycle(cycle_id: str, state: dict):
    try:
        from kafka import KafkaProducer
        import os
        producer = KafkaProducer(
            bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(","),
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        producer.send("feedback_metrics", value={"cycle_id": cycle_id, "state_keys": list(state.keys())})
        producer.flush()
    except Exception as e:
        logger.warning("Failed to publish cycle: %s", e)
