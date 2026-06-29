.PHONY: up up-fast down logs orchestrate connectors schemas init build pre-pull build-seq portal path-b

# Stable single-command bring-up: pre-pull base images, build sequentially
# (avoids PyPI/Docker Hub parallel timeouts), then start the full stack.
up: pre-pull build-seq
	docker compose up -d
	@echo "Stack starting. Run 'make health' in ~60s, then 'make connectors'."

# Fast path for warm caches (parallel build).
up-fast:
	docker compose up -d --build

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

stop-local:
	bash scripts/stop-local.sh

status:
	bash scripts/status-local.sh

pipeline-test:
	bash scripts/pipeline-test.sh

path-b:
	bash scripts/path-b-e2e.sh

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
