FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 kafka-python==2.0.2 prometheus-client==0.20.0
COPY exporter.py ./exporter.py
CMD ["python", "exporter.py"]
