FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 fastapi uvicorn httpx pydantic sqlalchemy psycopg2-binary
COPY shared/ ./shared/
COPY auditing-service/main.py ./main.py
ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8012"]
