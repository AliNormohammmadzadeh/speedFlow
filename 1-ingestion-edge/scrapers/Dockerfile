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
# The Playwright browser binary is downloaded from cdn.playwright.dev, which is
# geo-restricted in some regions (HTTP 403 "not available in your location").
# That download must not fail the image build: Selenium uses the apt "chromium"
# package installed above, and the REST/WebSocket scrapers need no browser. Keep
# the install attempt but make it non-fatal.
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    (playwright install chromium \
     || echo "WARNING: Playwright Chromium download unavailable (network/geo-restricted CDN); Selenium uses the apt 'chromium' package instead.")

COPY 1-ingestion-edge/scrapers/rest ./rest
COPY 1-ingestion-edge/scrapers/websocket ./websocket
COPY 1-ingestion-edge/scrapers/crawlee ./crawlee
COPY 1-ingestion-edge/scrapers/selenium ./selenium
COPY 1-ingestion-edge/scrapers/shared ./shared
COPY schemas/avro ./schemas/avro

CMD ["python", "-m", "shared.runner", "rest"]
