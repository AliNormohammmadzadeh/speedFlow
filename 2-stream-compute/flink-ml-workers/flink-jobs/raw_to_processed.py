"""Runnable PyFlink job: stateful tumbling-window aggregation.

Submit to the cluster with:
    flink run -py /opt/flink/usrlib/raw_to_processed.py

Reads JSON events from `flink_input`, keys them by symbol, applies a
tumbling processing-time window (stateful window operator), and writes the
per-window aggregate (count + average price) to `flink_windowed`.

This validates Flink stateful windowing running on the actual cluster. The
Avro production pipeline continues to be served by the stream-processor
service; this job demonstrates the Flink-native stateful path (Phase 3.1).
"""

import json
import os

from pyflink.common import Types
from pyflink.common.time import Time
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.window import TumblingProcessingTimeWindows

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
IN_TOPIC = os.environ.get("FLINK_INPUT_TOPIC", "flink_input")
OUT_TOPIC = os.environ.get("FLINK_OUTPUT_TOPIC", "flink_windowed")
WINDOW_SECONDS = int(os.environ.get("FLINK_WINDOW_SECONDS", "10"))


def to_kv(value: str):
    try:
        d = json.loads(value)
    except Exception:
        return ("unknown", 0.0, 1)
    symbol = str(d.get("symbol") or d.get("source_id") or "unknown")
    try:
        price = float(d.get("price", 0.0))
    except (TypeError, ValueError):
        price = 0.0
    return (symbol, price, 1)


def reduce_window(a, b):
    # Stateful reduce over the window: accumulate price sum and count.
    return (a[0], a[1] + b[1], a[2] + b[2])


def to_json(t) -> str:
    symbol, sum_price, count = t
    return json.dumps({
        "symbol": symbol,
        "window_count": count,
        "sum_price": sum_price,
        "avg_price": (sum_price / count) if count else 0.0,
        "processed_by": "flink",
    })


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_topics(IN_TOPIC)
        .set_group_id("flink-window-processor")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(BOOTSTRAP)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(OUT_TOPIC)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )

    stream = env.from_source(source, WatermarkStrategy.no_watermarks(), "kafka-raw-source")
    (
        stream.map(to_kv, output_type=Types.TUPLE([Types.STRING(), Types.DOUBLE(), Types.INT()]))
        .key_by(lambda t: t[0])
        .window(TumblingProcessingTimeWindows.of(Time.seconds(WINDOW_SECONDS)))
        .reduce(reduce_window)
        .map(to_json, output_type=Types.STRING())
        .sink_to(sink)
    )

    env.execute("raw_to_processed_windowed")


if __name__ == "__main__":
    main()
