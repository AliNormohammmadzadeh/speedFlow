# Stage 1 — build React UI
FROM node:20-alpine AS web
WORKDIR /web
COPY 5-ui/portal-web/package.json 5-ui/portal-web/package-lock.json* ./
RUN npm install
COPY 5-ui/portal-web/ .
RUN npm run build

# Stage 2 — API + static
FROM python:3.11-slim
WORKDIR /app
COPY 5-ui/portal-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY 5-ui/portal-api/main.py .
COPY --from=web /web/dist /app/static
ENV PORTAL_STATIC_DIR=/app/static
EXPOSE 8030
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8030"]
