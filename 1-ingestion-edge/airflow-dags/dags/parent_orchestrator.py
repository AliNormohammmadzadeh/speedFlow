"""Parameter-driven parent DAG: triggers scraper child DAGs and monitors lag.

Phase 3 (3.2): the parent DAG loads a vertical's seed sources and triggers a
child DAG per run, which enqueues real scraper/crawlee jobs into Redis (the same
queues the AI Scraper Bridge uses) and then monitors Kafka consumer-group lag,
failing (alerting) when lag exceeds a threshold.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

default_args = {
    "owner": "speedflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
STREAM_GROUP = os.environ.get("STREAM_CONSUMER_GROUP", "speedflow-stream-processor")
LAG_ALERT_THRESHOLD = int(os.environ.get("LAG_ALERT_THRESHOLD", "5000"))

CRAWLEE_QUEUE = os.environ.get("CRAWLEE_QUEUE", "crawlee:jobs")
SCRAPER_QUEUE = os.environ.get("SCRAPER_BRIDGE_QUEUE", "scraper:jobs")


def _load_verticals() -> dict:
    config_path = Path("/opt/airflow/config/business/verticals.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_pipeline_config(**context):
    params = context["params"]
    verticals = _load_verticals()
    vertical_id = params.get("vertical", verticals.get("default_vertical", "gaming_esports"))
    vertical = verticals.get("verticals", {}).get(vertical_id, {})
    context["ti"].xcom_push(key="vertical_config", value=vertical)
    context["ti"].xcom_push(key="vertical_id", value=vertical_id)
    return vertical_id


def _enqueue_sources(sources: list[dict]) -> dict:
    """Push seed sources into the same Redis queues the scrapers consume."""
    import redis

    client = redis.from_url(REDIS_URL)
    counts = {"crawlee": 0, "scraper": 0}
    for src in sources:
        stype = src.get("type", "rest")
        url = src.get("url")
        if not url:
            continue
        if stype == "crawlee":
            job = {
                "job_id": str(uuid.uuid4())[:12],
                "type": "crawlee",
                "source_id": src.get("name", "airflow-seed"),
                "urls": [url],
                "vertical": src.get("vertical", "unknown"),
                "event_type": "airflow_ingestion",
                "max_pages": int(src.get("max_pages", 3)),
                "tenant_id": "platform",
                "value_score": src.get("value_score"),
            }
            client.rpush(CRAWLEE_QUEUE, json.dumps(job))
            counts["crawlee"] += 1
        else:
            job = {
                "source_id": src.get("name", "airflow-seed"),
                "type": stype,
                "url": url,
                "vertical": src.get("vertical", "unknown"),
                "event_type": src.get("event_type", "airflow_ingestion"),
                "interval_seconds": int(src.get("interval_seconds", 60)),
                "value_score": src.get("value_score"),
            }
            client.rpush(SCRAPER_QUEUE, json.dumps(job))
            counts["scraper"] += 1
    print(f"Enqueued scraper jobs: {counts}")
    return counts


def enqueue_from_conf(**context):
    """Child-DAG task: enqueue sources passed via dag_run.conf."""
    conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
    sources = conf.get("sources", [])
    if not sources:
        verticals = _load_verticals()
        vid = conf.get("vertical", verticals.get("default_vertical", "gaming_esports"))
        sources = verticals.get("verticals", {}).get(vid, {}).get("seed_sources", [])
    counts = _enqueue_sources(sources)
    context["ti"].xcom_push(key="enqueued", value=counts)
    return counts


def monitor_kafka_lag(**context):
    """Compute stream-processor consumer lag; raise (alert) if above threshold."""
    from kafka import KafkaAdminClient, KafkaConsumer

    admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP.split(","))
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_BOOTSTRAP.split(","), group_id=None)
    try:
        offsets = admin.list_consumer_group_offsets(STREAM_GROUP)
        if not offsets:
            print(f"No committed offsets for group {STREAM_GROUP} yet (processor may be idle)")
            return 0
        end = consumer.end_offsets(list(offsets.keys()))
        total_lag = 0
        for tp, meta in offsets.items():
            committed = meta.offset if meta and meta.offset and meta.offset >= 0 else 0
            total_lag += max(0, end.get(tp, 0) - committed)
        print(f"Kafka consumer lag for {STREAM_GROUP}: {total_lag}")
        if total_lag > LAG_ALERT_THRESHOLD:
            raise AirflowException(
                f"ALERT: consumer lag {total_lag} exceeds threshold {LAG_ALERT_THRESHOLD}"
            )
        return total_lag
    finally:
        admin.close()
        consumer.close()


# --- Child DAG: enqueue scrapers for a vertical + monitor lag ---
with DAG(
    dag_id="scraper_ingestion",
    default_args=default_args,
    description="Child DAG: enqueue scraper/crawlee jobs from conf and monitor Kafka lag",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["speedflow", "ingestion", "child"],
    params={"vertical": "financial_markets"},
) as child_dag:
    enqueue = PythonOperator(task_id="enqueue_scrapers", python_callable=enqueue_from_conf)
    lag_check = PythonOperator(task_id="monitor_kafka_lag", python_callable=monitor_kafka_lag)
    enqueue >> lag_check


# --- Parent DAG: load vertical config, trigger the child DAG, validate health ---
with DAG(
    dag_id="parent_orchestrator",
    default_args=default_args,
    description="AI-configurable parent DAG that triggers ingestion child DAGs",
    schedule_interval=timedelta(hours=1),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["speedflow", "orchestration"],
    params={"vertical": "gaming_esports", "scale_factor": 1},
) as parent_dag:
    load_config = PythonOperator(task_id="load_pipeline_config", python_callable=load_pipeline_config)

    trigger_child = TriggerDagRunOperator(
        task_id="trigger_scraper_ingestion",
        trigger_dag_id="scraper_ingestion",
        conf={"vertical": "{{ params.vertical }}"},
        wait_for_completion=False,
        reset_dag_run=True,
    )

    health = PythonOperator(task_id="validate_pipeline_health", python_callable=monitor_kafka_lag)

    load_config >> trigger_child >> health
