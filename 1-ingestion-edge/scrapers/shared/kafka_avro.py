"""Confluent Avro serialization with Schema Registry."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

USE_AVRO = os.environ.get("USE_AVRO", "true").lower() in ("1", "true", "yes")


def _schema_dir() -> Path:
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    env_dir = os.environ.get("SCHEMA_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(Path("/app/schemas/avro"))
    # Walk up the directory tree looking for a schemas/avro folder (works for
    # both the deep host layout and the shallow /app layout inside images).
    for parent in here.parents:
        candidates.append(parent / "schemas" / "avro")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path("/app/schemas/avro")


def _load_schema(name: str) -> str:
    path = _schema_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Avro schema not found: {path}")
    return path.read_text()


@lru_cache(maxsize=1)
def _registry_client():
    from confluent_kafka.schema_registry import SchemaRegistryClient

    url = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    return SchemaRegistryClient({"url": url})


def register_schemas() -> dict[str, int]:
    """Register RawEvent and ProcessedEvent schemas; returns subject -> version."""
    if not USE_AVRO:
        return {}
    import urllib.request

    registry_url = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    subjects = {
        "raw_stream-value": "raw_event.avsc",
        "processed_stream-value": "processed_event.avsc",
    }
    versions: dict[str, int] = {}
    for subject, filename in subjects.items():
        schema_str = _load_schema(filename)
        payload = json.dumps({"schema": schema_str}).encode()
        req = urllib.request.Request(
            f"{registry_url}/subjects/{subject}/versions",
            data=payload,
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                versions[subject] = json.loads(resp.read())["id"]
                logger.info("Registered schema %s (id=%s)", subject, versions[subject])
        except Exception as exc:
            logger.warning("Schema registration for %s skipped: %s", subject, exc)
    return versions


def create_producer():
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    if not USE_AVRO:
        from kafka import KafkaProducer

        return KafkaProducer(
            bootstrap_servers=bootstrap.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )

    from confluent_kafka import Producer
    from confluent_kafka.schema_registry.avro import AvroSerializer
    from confluent_kafka.serialization import SerializationContext, MessageField

    client = _registry_client()
    schema_str = _load_schema("raw_event.avsc")
    serializer = AvroSerializer(client, schema_str)

    class AvroProducerWrapper:
        def __init__(self):
            self._producer = Producer({"bootstrap.servers": bootstrap})
            self._serializer = serializer

        def send(self, topic: str, key: str | None, value: dict) -> None:
            ctx = SerializationContext(topic, MessageField.VALUE)
            payload = self._serializer(value, ctx)
            self._producer.produce(topic, key=key, value=payload)
            self._producer.poll(0)

        def flush(self) -> None:
            self._producer.flush()

    return AvroProducerWrapper()


def create_processed_producer():
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    if not USE_AVRO:
        from kafka import KafkaProducer

        return KafkaProducer(
            bootstrap_servers=bootstrap.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )

    from confluent_kafka import Producer
    from confluent_kafka.schema_registry.avro import AvroSerializer
    from confluent_kafka.serialization import SerializationContext, MessageField

    client = _registry_client()
    schema_str = _load_schema("processed_event.avsc")
    serializer = AvroSerializer(client, schema_str)

    class AvroProducerWrapper:
        def __init__(self):
            self._producer = Producer({"bootstrap.servers": bootstrap})
            self._serializer = serializer

        def send(self, topic: str, key: str | None, value: dict) -> None:
            ctx = SerializationContext(topic, MessageField.VALUE)
            payload = self._serializer(value, ctx)
            self._producer.produce(topic, key=key.encode() if isinstance(key, str) else key, value=payload)
            self._producer.poll(0)

        def flush(self) -> None:
            self._producer.flush()

    return AvroProducerWrapper()


def create_consumer(topics: list[str], group_id: str, schema_file: str = "raw_event.avsc"):
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    if not USE_AVRO:
        from kafka import KafkaConsumer

        return KafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap.split(","),
            auto_offset_reset="earliest",
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

    from confluent_kafka import Consumer
    from confluent_kafka.schema_registry.avro import AvroDeserializer
    from confluent_kafka.serialization import SerializationContext, MessageField

    client = _registry_client()
    deserializer = AvroDeserializer(client, _load_schema(schema_file))

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe(topics)

    class AvroConsumerWrapper:
        def __init__(self):
            self._consumer = consumer
            self._deserializer = deserializer

        def poll(self, timeout_ms: int = 1000) -> dict:
            msg = self._consumer.poll(timeout_ms / 1000.0)
            if msg is None:
                return {}
            if msg.error():
                logger.error("Consumer error: %s", msg.error())
                return {}
            ctx = SerializationContext(msg.topic(), MessageField.VALUE)
            value = self._deserializer(msg.value(), ctx)
            return {msg.topic(): [{"value": value, "key": msg.key()}]}

        def close(self) -> None:
            self._consumer.close()

    return AvroConsumerWrapper()
