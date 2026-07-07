.PHONY: up up-fast down logs orchestrate connectors schemas init build pre-pull build-seq pre-docker-up portal path-b observability up-airflow flink-job secrets-demo dr-demo tf-plan k8s-validate start-serving

# Stable single-command bring-up: pre-pull base images, build sequentially
# (avoids PyPI/Docker Hub parallel timeouts), then start the full stack.
up: pre-pull build-seq pre-docker-up
	docker compose up -d
	@echo "Stack starting. Run 'make health' in ~60s, then 'make connectors'."

# Fast path for warm caches (parallel build).
up-fast: pre-docker-up
	docker compose up -d --build

pre-docker-up:
	bash scripts/pre-docker-up.sh

down:
	docker compose down

pre-pull:
	bash scripts/pre-pull-images.sh

build-seq:
	bash scripts/docker-build-all.sh

build:
	docker compose build

logs:
	docker compose logs -f

orchestrate:
	curl -s -X POST http://localhost:8000/orchestrate \
		-H "Content-Type: application/json" \
		-d '{"business_goals":["maximize_revenue"],"run_bridges":true}' | python3 -m json.tool

connectors:
	CONNECTOR_DIR=infra/kafka-connect KAFKA_CONNECT_URL=http://localhost:8083 bash scripts/register-connectors.sh

schemas:
	bash scripts/register-schemas.sh

portal:
	@echo "SpeedFlow Portal: http://localhost:8030"

start-local:
	bash scripts/start-local.sh

install-local-deps:
	bash scripts/install-local-deps.sh

start-apps:
	bash scripts/start-apps.sh

start-pipeline:
	bash scripts/start-pipeline.sh

# Serving-layer apps on host (trading bot :8011, marketplace :8014) — Phase 5 features
start-serving:
	bash scripts/start-serving-local.sh

stop-local:
	bash scripts/stop-local.sh

status:
	bash scripts/status-local.sh

pipeline-test:
	bash scripts/pipeline-test.sh

path-b:
	bash scripts/path-b-e2e.sh

# --- Phase 4 local emulation (no cloud account needed) ---
# Vault dev backend + orchestrator resolving secrets from it
secrets-demo:
	docker compose -f docker-compose.yml -f docker-compose.secrets.yml up -d vault ai-orchestrator
	@echo "Write a secret: docker exec platform-vault vault kv put secret/speedflow DEMO_SECRET=from-vault"

# Second Kafka cluster + MirrorMaker 2 cross-region replication
dr-demo:
	docker compose -f docker-compose.yml -f docker-compose.dr.yml up -d kafka-dr mirrormaker
	@echo "Verify: docker exec platform-kafka-dr kafka-topics --bootstrap-server kafka-dr:9092 --list"

# Offline terraform plan for the full MSK/EKS/RDS/ElastiCache graph
tf-plan:
	bash scripts/tf-plan.sh

# Validate GitOps k8s manifests against real Kubernetes schemas (kubeconform)
k8s-validate:
	kubeconform -summary -strict infra/gitops/k8s/*.yaml
	kubeconform -summary -ignore-missing-schemas infra/gitops/argocd/*.yaml infra/gitops/argocd/apps/*.yaml

# Submit the PyFlink stateful-window job to the Flink cluster (custom PyFlink image)
flink-job:
	docker compose -f docker-compose.yml -f docker-compose.flink.yml up -d --build flink-jobmanager flink-taskmanager flink-job-submitter
	@echo "Flink dashboard: http://localhost:8082 — look for 'raw_to_processed_windowed'"

# Optional Airflow stack (:8080, admin/admin) — parent + child ingestion DAGs
up-airflow:
	docker compose -f docker-compose.yml -f docker-compose.airflow.yml up -d --build airflow-init airflow
	@echo "Airflow: http://localhost:8080 (admin/admin)"

# Observability stack: Prometheus (:9090) + Grafana (:3000, admin/admin) + Kafka lag exporter (:9110)
observability:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d --build kafka-lag-exporter prometheus grafana
	@echo "Prometheus: http://localhost:9090 | Grafana: http://localhost:3000 (admin/admin)"

# Multi-tenant platform
tenant-create:
	curl -s -X POST http://localhost:8020/tenants \
		-H "Content-Type: application/json" \
		-d '{"name":"Demo Corp","plan":"pro","email":"demo@example.com"}' | python3 -m json.tool

scrape-request:
	@test -n "$(API_KEY)" || (echo "Set API_KEY=sf_..." && exit 1)
	curl -s -X POST http://localhost:8020/scrape \
		-H "Content-Type: application/json" \
		-H "X-API-Key: $(API_KEY)" \
		-d '{"requirement":"Scrape product prices from https://httpbin.org/html","max_pages":5}' | python3 -m json.tool

health:
	@echo "=== Service Health ==="
	@curl -sf http://localhost:8020/health && echo " Platform API OK" || echo " Platform API DOWN"
	@curl -sf http://localhost:8000/health && echo " AI Orchestrator OK" || echo " AI Orchestrator DOWN"
	@curl -sf http://localhost:8010/health && echo " Aggregator OK" || echo " Aggregator DOWN"
	@curl -sf http://localhost:8011/health && echo " Trading Bot OK" || echo " Trading Bot DOWN"
	@curl -sf http://localhost:8012/health && echo " Auditing OK" || echo " Auditing DOWN"
	@curl -sf http://localhost:8013/health && echo " Dashboard OK" || echo " Dashboard DOWN"
	@curl -sf http://localhost:8014/health && echo " Marketplace OK" || echo " Marketplace DOWN"
	@curl -sf http://localhost:8030/api/overview > /dev/null && echo " UI Portal OK" || echo " UI Portal DOWN"
