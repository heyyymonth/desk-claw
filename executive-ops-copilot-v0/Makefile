.PHONY: build-frontend build-web-backend build-ai-backend build-eval-backend build-eval-frontend build-all run-all lint-frontend lint-web-backend lint-ai-backend lint-eval-backend lint-eval-frontend lint-all test-frontend test-web-backend test-ai-backend test-eval-backend test-eval-frontend test-all run-evals smoke-containers health health-providers

FRONTEND_HOST_PORT ?= 3000
WEB_BACKEND_HOST_PORT ?= 8000
AI_BACKEND_HOST_PORT ?= 9000
EVAL_BACKEND_HOST_PORT ?= 9300
EVAL_FRONTEND_HOST_PORT ?= 3300

build-frontend:
	docker compose build frontend

build-web-backend:
	docker compose build web-backend

build-ai-backend:
	docker compose build ai-backend

build-eval-backend:
	docker compose build eval-backend

build-eval-frontend:
	docker compose build eval-frontend

build-all:
	docker compose build

run-all:
	docker compose up

lint-frontend:
	cd frontend && npm run lint

lint-web-backend:
	cd web_backend && python3 -m ruff check app tests

lint-ai-backend:
	cd ai_backend && python3 -m ruff check .

lint-eval-backend:
	cd eval_backend && python3 -m ruff check app tests

lint-eval-frontend:
	cd eval_frontend && npm run lint

lint-all: lint-web-backend lint-ai-backend lint-eval-backend lint-frontend lint-eval-frontend

test-frontend:
	cd frontend && npm test -- --run

test-web-backend:
	cd web_backend && python3 -m pytest

test-ai-backend:
	cd ai_backend && python3 -m pytest

test-eval-backend:
	cd eval_backend && python3 -m pytest

test-eval-frontend:
	cd eval_frontend && npm test -- --run

test-all: test-web-backend test-ai-backend test-eval-backend test-frontend test-eval-frontend

run-evals:
	curl -fsS -X POST http://localhost:$(EVAL_BACKEND_HOST_PORT)/api/eval-runs | python3 -m json.tool

smoke-containers:
	FRONTEND_HOST_PORT=$(FRONTEND_HOST_PORT) WEB_BACKEND_HOST_PORT=$(WEB_BACKEND_HOST_PORT) AI_BACKEND_HOST_PORT=$(AI_BACKEND_HOST_PORT) EVAL_BACKEND_HOST_PORT=$(EVAL_BACKEND_HOST_PORT) EVAL_FRONTEND_HOST_PORT=$(EVAL_FRONTEND_HOST_PORT) docker compose down -v
	FRONTEND_HOST_PORT=$(FRONTEND_HOST_PORT) WEB_BACKEND_HOST_PORT=$(WEB_BACKEND_HOST_PORT) AI_BACKEND_HOST_PORT=$(AI_BACKEND_HOST_PORT) EVAL_BACKEND_HOST_PORT=$(EVAL_BACKEND_HOST_PORT) EVAL_FRONTEND_HOST_PORT=$(EVAL_FRONTEND_HOST_PORT) docker compose up -d --build
	@trap 'docker compose down -v' EXIT; \
	for url in http://localhost:$(AI_BACKEND_HOST_PORT)/health http://localhost:$(AI_BACKEND_HOST_PORT)/health/providers http://localhost:$(WEB_BACKEND_HOST_PORT)/health http://localhost:$(FRONTEND_HOST_PORT)/ http://localhost:$(EVAL_BACKEND_HOST_PORT)/health http://localhost:$(EVAL_FRONTEND_HOST_PORT)/; do \
		echo "Checking $$url"; \
		for i in $$(seq 1 60); do \
			curl -fsS "$$url" >/dev/null && break; \
			if [ "$$i" = 60 ]; then docker compose ps; docker compose logs --no-color; exit 1; fi; \
			sleep 2; \
		done; \
	done; \
	docker compose exec -T web-backend python -c "import json, urllib.request; body=json.loads(urllib.request.urlopen('http://ai-backend:9000/health', timeout=5).read().decode()); assert body['service'] == 'ai-backend'"
	docker compose exec -T eval-backend python -c "import json, urllib.request; body=json.loads(urllib.request.urlopen('http://ai-backend:9000/health', timeout=5).read().decode()); assert body['service'] == 'ai-backend'"

health:
	curl -fsS http://localhost:8000/health && echo
	curl -fsS http://localhost:9000/health && echo
	curl -fsS http://localhost:9300/health && echo

health-providers:
	curl -fsS http://localhost:9000/health/providers && echo
