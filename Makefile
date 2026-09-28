.PHONY: help install install-backend install-frontend dev test seed-demo reset-demo \
	run-demo export serve docker-up docker-down docker-build tree clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install backend + frontend dependencies

install-backend: ## Install backend dependencies
	cd backend && python3 -m pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

dev: ## Run backend + frontend locally (SQLite, zero setup)
	./scripts/dev.sh

test: ## Run backend test suite
	cd backend && python3 -m pytest -q

seed-demo: ## Load the 100-company synthetic dataset
	cd backend && python3 -m leadforge seed-demo

reset-demo: ## Wipe demo data (jobs, companies, results)
	cd backend && python3 -m leadforge reset-demo

run-demo: ## Run the demo pipeline headless (Jewelry Stores / US / CA / 100)
	cd backend && python3 -m leadforge run-demo --industry "Jewelry Stores" \
		--country "United States" --region California --leads 100

export: ## Export a job's dataset: make export JOB=<id> FORMAT=xlsx OUT=leads.xlsx
	cd backend && python3 -m leadforge export --job "$(JOB)" --format "$(FORMAT)" --out "$(OUT)"

serve: ## Run the API server (dev)
	cd backend && python3 -m leadforge serve

docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start the full stack with Docker Compose
	docker compose up

docker-down: ## Stop the Docker Compose stack
	docker compose down

tree: ## Show the repository tree
	find . -path ./node_modules -prune -o -path ./.git -prune -o -print | sort

clean: ## Remove caches and local dev databases
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name "*.db" -delete
	rm -rf backend/htmlcov backend/.coverage
