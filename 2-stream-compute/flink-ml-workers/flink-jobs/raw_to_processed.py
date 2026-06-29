"""
Reference PyFlink job template.
Submit via: flink run -py flink_jobs/raw_to_processed.py
Requires PyFlink in Flink cluster (custom image for production).
"""

# MVP note: The docker-compose stream-processor service handles this pipeline.
# This file documents the Flink-native implementation path for Phase 4 AI injection.

FLINK_JOB_TEMPLATE = """
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors import FlinkKafkaConsumer, FlinkKafkaProducer
from pyflink.common.serialization import SimpleStringSchema

env = StreamExecutionEnvironment.get_execution_environment()

consumer = FlinkKafkaConsumer(
    topics='raw_stream',
    deserialization_schema=SimpleStringSchema(),
    properties={'bootstrap.servers': 'kafka:9092', 'group.id': 'flink-processor'}
)

producer = FlinkKafkaProducer(
    topic='processed_stream',
    serialization_schema=SimpleStringSchema(),
    producer_config={'bootstrap.servers': 'kafka:9092'}
)

# AI-injectable processing function placeholder
def process_json(value):
    import json
    data = json.loads(value)
    data['processed_by'] = 'flink'
    return json.dumps(data)

stream = env.add_source(consumer).map(process_json)
stream.add_sink(producer)
env.execute('raw_to_processed')
"""

if __name__ == "__main__":
    print("PyFlink job template (see FLINK_JOB_TEMPLATE in source)")
    print("Use stream-processor service for MVP, or build custom Flink+PyFlink image.")
