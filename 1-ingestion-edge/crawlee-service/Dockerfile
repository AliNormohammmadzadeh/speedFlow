FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev gcc \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY 1-ingestion-edge/crawlee-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium

COPY 1-ingestion-edge/crawlee-service/crawler.py 1-ingestion-edge/crawlee-service/worker.py ./
COPY 1-ingestion-edge/crawlee-service/config/ ./config/
COPY 1-ingestion-edge/scrapers/shared/ ./shared/
COPY schemas/avro ./schemas/avro

ENV PYTHONPATH=/app

CMD ["python", "worker.py"]
