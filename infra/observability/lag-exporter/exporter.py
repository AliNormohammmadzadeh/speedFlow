"""Kafka consumer-group lag Prometheus exporter for SpeedFlow.

Computes lag for the stream-processor consumer group across all raw_stream*
topics and exposes it at :9110/metrics as speedflow_consumer_group_lag.
"""

import logging
import os
import time

from kafka import KafkaAdminClient, KafkaConsumer, TopicPartition
from prometheus_client import Gauge, start_http_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s [lag-exporter] %(message)s")
logger = logging.getLogger(__name__)

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
GROUPS = [g for g in os.environ.get("CONSUMER_GROUPS", "speedflow-stream-processor").split(",") if g]
PORT = int(os.environ.get("METRICS_PORT", "9110"))
INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_SECONDS", "15"))

LAG = Gauge("speedflow_consumer_group_lag", "Consumer group lag (messages)", ["group", "topic"])
TOTAL_LAG = Gauge("speedflow_consumer_group_lag_total", "Total consumer group lag", ["group"])


def collect_once(consumer: KafkaConsumer, admin: KafkaAdminClient) -> None:
    for group in GROUPS:
        try:
            offsets = admin.list_consumer_group_offsets(group)
        except Exception as exc:
            logger.warning("group %s offsets unavailable: %s", group, exc)
            continue
        if not offsets:
            continue
        end_offsets = consumer.end_offsets(list(offsets.keys()))
        per_topic: dict[str, int] = {}
        for tp, meta in offsets.items():
            committed = meta.offset if meta and meta.offset is not None and meta.offset >= 0 else 0
            end = end_offsets.get(tp, 0)
            lag = max(0, end - committed)
            per_topic[tp.topic] = per_topic.get(tp.topic, 0) + lag
        total = 0
        for topic, lag in per_topic.items():
            LAG.labels(group=group, topic=topic).set(lag)
            total += lag
        TOTAL_LAG.labels(group=group).set(total)
        logger.info("group=%s total_lag=%d topics=%d", group, total, len(per_topic))


def main() -> None:
    start_http_server(PORT)
    logger.info("Kafka lag exporter on :%d/metrics (groups=%s)", PORT, GROUPS)
    consumer = None
    admin = None
    while True:
        try:
            if consumer is None:
                consumer = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None)
            if admin is None:
                admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP)
            collect_once(consumer, admin)
        except Exception as exc:
            logger.warning("collection error: %s", exc)
            consumer = None
            admin = None
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
