FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/ ./agents/
COPY bridges/ ./bridges/
COPY orchestrator/ ./orchestrator/

ENV PYTHONPATH=/app
ENV CONFIG_PATH=/app/config

CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
