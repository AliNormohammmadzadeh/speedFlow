FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 fastapi uvicorn kafka-python httpx pydantic "confluent-kafka[avro,schemaregistry]>=2.3.0"
COPY shared/ ./shared/
COPY trading-bot/main.py ./main.py
ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
