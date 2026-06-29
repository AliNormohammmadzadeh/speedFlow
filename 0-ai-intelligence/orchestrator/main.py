"""AI Orchestrator - coordinates multi-agent swarm."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
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

    strategy_out = await strategy_agent.run(state, feedback=req.feedback)
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
    """Receive performance metrics from end-use apps."""
    client = redis.from_url(__import__("os").environ.get("REDIS_URL", "redis://localhost:6379/0"))
    for name, value in req.metrics.items():
        client.rpush("feedback:metrics", json.dumps({
            "app_name": req.app_name,
            "metric_name": name,
            "metric_value": value,
        }))
    return {"status": "recorded", "app": req.app_name, "metrics_count": len(req.metrics)}


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
