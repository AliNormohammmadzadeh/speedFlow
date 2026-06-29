FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn redis scikit-learn numpy pydantic
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
