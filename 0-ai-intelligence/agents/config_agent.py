"""Platform Infrastructure Configuration Agent (Ops)."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.utils import AgentState, llm_complete

logger = logging.getLogger(__name__)


class ConfigAgent:
    """Generates Terraform/K8s configs for desired platform state."""

    name = "config"

    async def run(self, state: AgentState, desired_state: dict | None = None) -> dict[str, Any]:
        desired = desired_state or {
            "kafka_partitions": 6,
            "flink_parallelism": 4,
            "scraper_replicas": 2,
            "scale_factor": 1.0,
        }
        processing = state.get("processing_output", {})
        if processing.get("primary_strategy") == "flink_stateful":
            desired["flink_parallelism"] = max(desired.get("flink_parallelism", 4), 4)

        tf_config = self._generate_terraform(desired)
        k8s_config = self._generate_k8s_manifests(desired)
        airflow_params = self._generate_airflow_params(state)

        prompt = f"Review platform scaling config: {desired}"
        llm_review = await llm_complete(prompt, system="You are a platform DevOps engineer.")

        output_dir = Path(os.environ.get("GITOPS_REPO_PATH", "/tmp/speedflow-gitops"))
        output_dir.mkdir(parents=True, exist_ok=True)
        self._write_gitops(output_dir, tf_config, k8s_config)

        result = {
            "desired_state": desired,
            "terraform": tf_config,
            "kubernetes": k8s_config,
            "airflow_params": airflow_params,
            "gitops_path": str(output_dir),
            "llm_review": llm_review,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        state.set("config_output", result)
        logger.info("Config agent: generated TF + K8s to %s", output_dir)
        return result

    def _generate_terraform(self, desired: dict) -> dict:
        return {
            "resource": {
                "aws_msk_cluster": {
                    "speedflow_kafka": {
                        "cluster_name": "speedflow-kafka",
                        "kafka_version": "3.5.1",
                        "number_of_broker_nodes": desired.get("kafka_brokers", 3),
                        "broker_node_group_info": {
                            "instance_type": "kafka.m5.large",
                            "storage_info": {"ebs_storage_info": {"volume_size": 100}},
                        },
                    }
                }
            },
            "variable": {
                "kafka_partitions": {"default": desired.get("kafka_partitions", 3)},
                "flink_parallelism": {"default": desired.get("flink_parallelism", 4)},
            },
        }

    def _generate_k8s_manifests(self, desired: dict) -> list[dict]:
        return [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "scraper-rest", "labels": {"app": "speedflow-scraper"}},
                "spec": {
                    "replicas": desired.get("scraper_replicas", 1),
                    "selector": {"matchLabels": {"app": "speedflow-scraper"}},
                    "template": {
                        "metadata": {"labels": {"app": "speedflow-scraper"}},
                        "spec": {
                            "containers": [{
                                "name": "scraper",
                                "image": "speedflow/scraper-rest:latest",
                                "env": [{"name": "KAFKA_BOOTSTRAP_SERVERS", "value": "kafka:9092"}],
                            }]
                        },
                    },
                },
            },
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "flink-taskmanager"},
                "spec": {
                    "replicas": desired.get("flink_parallelism", 4) // 2,
                    "template": {"spec": {"containers": [{"name": "taskmanager", "image": "flink:1.18"}]}},
                },
            },
        ]

    def _generate_airflow_params(self, state: AgentState) -> dict:
        discovery = state.get("discovery_output", {})
        verticals = {s.get("vertical") for s in discovery.get("discovered_sources", [])}
        return {
            "dag_id": "dynamic_vertical_pipeline",
            "conf": {"vertical": next(iter(verticals), "gaming_esports"), "action": "run"},
        }

    def _write_gitops(self, output_dir: Path, tf: dict, k8s: list[dict]) -> None:
        (output_dir / "terraform").mkdir(exist_ok=True)
        (output_dir / "k8s").mkdir(exist_ok=True)
        with open(output_dir / "terraform" / "generated.tf.json", "w") as f:
            json.dump(tf, f, indent=2)
        for i, manifest in enumerate(k8s):
            name = manifest.get("metadata", {}).get("name", f"manifest-{i}")
            with open(output_dir / "k8s" / f"{name}.json", "w") as f:
                json.dump(manifest, f, indent=2)
