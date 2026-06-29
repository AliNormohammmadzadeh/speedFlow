"""Parameter-driven parent DAG for dynamic ingestion and processing orchestration."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
import yaml
from pathlib import Path


default_args = {
    "owner": "speedflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def load_pipeline_config(**context):
    """Load vertical/pipeline config passed via DAG params or config file."""
    params = context["params"]
    config_path = Path("/opt/airflow/config/business/verticals.yaml")
    verticals = {}
    if config_path.exists():
        with open(config_path) as f:
            verticals = yaml.safe_load(f) or {}
    vertical_id = params.get("vertical", verticals.get("default_vertical", "gaming_esports"))
    vertical = verticals.get("verticals", {}).get(vertical_id, {})
    context["ti"].xcom_push(key="vertical_config", value=vertical)
    context["ti"].xcom_push(key="vertical_id", value=vertical_id)
    return vertical_id


def trigger_ingestion(**context):
    vertical = context["ti"].xcom_pull(key="vertical_config")
    sources = vertical.get("seed_sources", [])
    print(f"Orchestrating ingestion for {len(sources)} seed sources")
    for source in sources:
        print(f"  - {source['name']} ({source['type']}): {source['url']}")
    return len(sources)


def trigger_processing(**context):
    vertical = context["ti"].xcom_pull(key="vertical_config")
    pipelines = vertical.get("reference_pipelines", [])
    for pipeline in pipelines:
        print(f"Processing pipeline: {pipeline.get('flink_job')} -> {pipeline.get('ml_model')}")
    return len(pipelines)


def validate_pipeline_health(**context):
    """Placeholder health check - extend with Kafka/Flink API calls."""
    print("Pipeline health check: OK (MVP stub)")
    return True


with DAG(
    dag_id="parent_orchestrator",
    default_args=default_args,
    description="AI-configurable parent DAG for any vertical pipeline",
    schedule_interval=timedelta(hours=1),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["speedflow", "orchestration"],
    params={
        "vertical": "gaming_esports",
        "scale_factor": 1,
    },
) as parent_dag:
    load_config = PythonOperator(
        task_id="load_pipeline_config",
        python_callable=load_pipeline_config,
    )
    ingest = PythonOperator(
        task_id="trigger_ingestion",
        python_callable=trigger_ingestion,
    )
    process = PythonOperator(
        task_id="trigger_processing",
        python_callable=trigger_processing,
    )
    health = PythonOperator(
        task_id="validate_pipeline_health",
        python_callable=validate_pipeline_health,
    )
    load_config >> ingest >> process >> health


with DAG(
    dag_id="dynamic_vertical_pipeline",
    default_args=default_args,
    description="Triggered per-vertical pipeline (invoked by AI Config Agent or parent DAG)",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["speedflow", "dynamic"],
    params={"vertical": "financial_markets", "action": "run"},
) as dynamic_dag:
    run_vertical = PythonOperator(
        task_id="run_vertical_pipeline",
        python_callable=load_pipeline_config,
    )
