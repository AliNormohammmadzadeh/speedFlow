FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev gcc \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY 1-ingestion-edge/crawlee-service/requirements.txt .
# The Playwright Python package is required, but the browser binary is downloaded
# from cdn.playwright.dev, which is geo-restricted in some regions (HTTP 403
# "not available in your location"). That download must not fail the image build:
# the default crawl path uses BeautifulSoupCrawler (no browser) and there is an
# HTTP fallback crawler, so Chromium is optional. Keep the install attempt but
# make it non-fatal.
RUN pip install --no-cache-dir -r requirements.txt \
    && (playwright install chromium \
        || echo "WARNING: Playwright Chromium download unavailable (network/geo-restricted CDN); crawlee will use the BeautifulSoup/HTTP fallback crawler.")

COPY 1-ingestion-edge/crawlee-service/crawler.py 1-ingestion-edge/crawlee-service/worker.py ./
COPY 1-ingestion-edge/crawlee-service/config/ ./config/
COPY 1-ingestion-edge/scrapers/shared/ ./shared/
COPY schemas/avro ./schemas/avro

ENV PYTHONPATH=/app

CMD ["python", "worker.py"]
