.PHONY: build-frontend build-web-backend build-ai-backend build-all run-all test-frontend test-web-backend test-ai-backend test-all health health-providers

build-frontend:
	docker compose build frontend

build-web-backend:
	docker compose build web-backend

build-ai-backend:
	docker compose build ai-backend

build-all:
	docker compose build

run-all:
	docker compose up

test-frontend:
	cd frontend && npm test -- --run

test-web-backend:
	cd web_backend && python3 -m pytest

test-ai-backend:
	cd ai_backend && python3 -m pytest

test-all: test-web-backend test-ai-backend test-frontend

health:
	curl -fsS http://localhost:8000/health && echo
	curl -fsS http://localhost:9000/health && echo

health-providers:
	curl -fsS http://localhost:9000/health/providers && echo
