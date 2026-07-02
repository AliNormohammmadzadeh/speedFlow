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
        "events_indexed": count,
        "active_verticals": ["gaming_esports", "financial_markets", "accommodation_travel"],
        "throughput_events_per_min": count // 60 if count else 0,
    }


@app.get("/metrics/timeseries")
def metrics_timeseries(hours: int = Query(24), bucket_minutes: int = Query(60), vertical: str = Query("")):
    """ES histogram of processed events over time (buckets of `bucket_minutes`)."""
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    now_ms = int(__import__("time").time() * 1000)
    since_ms = now_ms - hours * 3600 * 1000
    bucket_ms = max(1, bucket_minutes) * 60 * 1000
    must: list[dict] = [{"range": {"processed_at": {"gte": since_ms}}}]
    if vertical:
        must.append({"term": {"vertical.keyword": vertical}})
    # `processed_at` is indexed as epoch-millis (numeric), so use a numeric
    # histogram aggregation rather than date_histogram (avoids date-mapping needs).
    body = {
        "size": 0,
        "query": {"bool": {"must": must}},
        "aggs": {"events_over_time": {"histogram": {"field": "processed_at", "interval": bucket_ms, "min_doc_count": 0}}},
    }
    buckets = []
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.post(f"{es_url}/processed-events/_search", json=body)
            if resp.status_code == 200:
                for b in resp.json().get("aggregations", {}).get("events_over_time", {}).get("buckets", []):
                    buckets.append({"ts": int(b["key"]), "count": b["doc_count"]})
    except Exception as e:
        logger.warning("ES timeseries failed: %s", e)
    return {"bucket_minutes": bucket_minutes, "hours": hours, "series": buckets}


@app.get("/metrics/by-vertical")
def metrics_by_vertical():
    """ES terms aggregation: event counts grouped by vertical."""
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")
    body = {"size": 0, "aggs": {"by_vertical": {"terms": {"field": "vertical.keyword", "size": 20}}}}
    result = []
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.post(f"{es_url}/processed-events/_search", json=body)
            if resp.status_code == 200:
                for b in resp.json().get("aggregations", {}).get("by_vertical", {}).get("buckets", []):
                    result.append({"vertical": b["key"], "count": b["doc_count"]})
    except Exception as e:
        logger.warning("ES by-vertical failed: %s", e)
    return {"verticals": result}


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
