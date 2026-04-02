# inVision U — convenience commands (wraps scripts/*.sh)
# Usage: make help | make frontend | make backend | ...
#
# Note: a real directory named `infra/` exists — all targets below are phony
# so `make infra` runs the recipe instead of skipping as "up to date".

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help install install-frontend install-api infra frontend backend worker dev migrate init-db seed docker-up docker-down smoke smoke-services test-integration test-e2e check-invariants

help:
	@echo "inVision U — commands"
	@echo ""
	@echo "  make install          - pnpm install + Python venv + pip (API)"
	@echo "  make install-frontend - only Node/pnpm dependencies"
	@echo "  make install-api      - only Python venv + requirements"
	@echo ""
	@echo "  make infra            - docker compose: postgres + redis (detached)"
	@echo "  make frontend         - Next.js dev (port 3000)"
	@echo "  make backend          - FastAPI + auto-start validation services + migrations/seed"
	@echo "  make worker           - Redis job worker (admission_jobs queue)"
	@echo "  make dev              - start backend + worker + frontend together (3 panes)"
	@echo ""
	@echo "  make migrate          - alembic upgrade head"
	@echo "  make init-db          - create POSTGRES_USER / POSTGRES_DB on local Postgres (if role missing)"
	@echo "  make seed             - seed roles + internal test questions"
	@echo ""
	@echo "  make docker-up        - docker compose up --build (full stack)"
	@echo "  make docker-down      - docker compose down"
	@echo "  make smoke            - pytest (API) + vitest (web)"
	@echo "  make smoke-services   - HTTP smoke for backend + validation services"
	@echo ""
	@echo "  make test-integration - run integration tests (excludes e2e)"
	@echo "  make test-e2e         - run end-to-end pipeline test"
	@echo "  make check-invariants - verify pipeline data-integrity invariants"
	@echo ""
	@echo "Direct scripts (same as above): ./scripts/frontend.sh, ./scripts/backend.sh, …"

install: install-frontend install-api

install-frontend:
	@bash scripts/install-frontend.sh

install-api:
	@bash scripts/install-api.sh

infra:
	@bash scripts/infra.sh

frontend:
	@bash scripts/frontend.sh

backend:
	@bash scripts/backend.sh

worker:
	@bash scripts/worker.sh

dev:
	@if command -v tmux >/dev/null 2>&1; then \
		SESSION="invision-dev"; \
		tmux new-session -d -s $$SESSION -n backend "bash scripts/backend.sh" 2>/dev/null || true; \
		tmux new-window -t $$SESSION -n worker "bash scripts/worker.sh"; \
		tmux new-window -t $$SESSION -n frontend "bash scripts/frontend.sh"; \
		tmux select-window -t $$SESSION:backend; \
		echo "Started 3 tmux windows in session '$$SESSION'. Attach with: tmux attach -t $$SESSION"; \
	else \
		echo "tmux not found — start these in separate terminals:"; \
		echo "  make backend"; \
		echo "  make worker"; \
		echo "  make frontend"; \
	fi

migrate:
	@bash scripts/migrate.sh

init-db:
	@bash scripts/init-local-postgres.sh

seed:
	@bash scripts/seed.sh

docker-up:
	@bash scripts/docker-up.sh

docker-down:
	@bash scripts/docker-down.sh

smoke:
	@bash scripts/smoke.sh

smoke-services:
	@bash scripts/smoke-services.sh

test-integration:
	cd apps/api && PYTHONPATH=src python3 -m pytest tests/ -v --tb=short -x -k "not e2e"

test-e2e:
	cd apps/api && PYTHONPATH=src RUN_E2E=1 python3 -m pytest tests/test_e2e_pipeline.py -v --tb=short

check-invariants:
	@set -a && [ -f .env ] && . ./.env; set +a && cd apps/api && PYTHONPATH=src python3 ../../scripts/check_pipeline_invariants.py
