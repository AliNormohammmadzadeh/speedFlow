FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    libxml2-dev \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONPATH=/app

COPY 1-ingestion-edge/scrapers/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    playwright install chromium

COPY 1-ingestion-edge/scrapers/rest ./rest
COPY 1-ingestion-edge/scrapers/websocket ./websocket
COPY 1-ingestion-edge/scrapers/crawlee ./crawlee
COPY 1-ingestion-edge/scrapers/selenium ./selenium
COPY 1-ingestion-edge/scrapers/shared ./shared
COPY schemas/avro ./schemas/avro

CMD ["python", "-m", "shared.runner", "rest"]
