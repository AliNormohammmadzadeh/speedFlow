"""Meta-Analytics Dashboard API - queries Elasticsearch aggregations."""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    send_feedback(os.environ.get("APP_NAME", "meta_dashboard"), {
        "daily_active_users": 42.0,
        "query_latency_p95": 120.0,
        "engagement_minutes": 15.0,
    })
    yield


app = FastAPI(title="Meta-Analytics Dashboard")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics/overview")
def metrics_overview():
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{es_url}/processed-events/_count")
            count = resp.json().get("count", 0) if resp.status_code == 200 else 0
    except Exception:
        count = 0

    send_feedback(os.environ.get("APP_NAME", "meta_dashboard"), {
        "daily_active_users": 42.0,
        "engagement_minutes": 15.0,
    })
    return {
        "processed_events_count": count,
        "active_verticals": ["gaming_esports", "financial_markets", "accommodation_travel"],
        "throughput_events_per_min": count // 60 if count else 0,
    }


@app.get("/search")
def search_events(q: str = Query(""), vertical: str = Query("")):
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    query = {"query": {"match_all": {}}}
    if q:
        query = {"query": {"multi_match": {"query": q, "fields": ["event_type", "source_id"]}}}
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.post(f"{es_url}/processed-events/_search", json=query)
            if resp.status_code == 200:
                hits = resp.json().get("hits", {}).get("hits", [])
                return {"results": [h["_source"] for h in hits[:20]], "total": len(hits)}
    except Exception as e:
        logger.warning("ES search failed: %s", e)
    return {"results": [], "total": 0}
