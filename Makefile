# inVision U — convenience commands (wraps scripts/*.sh)
# Usage: make help | make frontend | make backend | ...
#
# Note: a real directory named `infra/` exists — all targets below are phony
# so `make infra` runs the recipe instead of skipping as "up to date".

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help install install-frontend install-api infra frontend backend worker migrate init-db seed docker-up docker-down smoke smoke-services

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
	@echo "  make worker           - Redis job worker (scaffold)"
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
