.PHONY: dev dev-d prod deploy down logs shell migrate createsuperuser

REGISTRY  = ghcr.io/shoenot/propraetor
TAG       ?= latest

# --- Development (build from source, hot reload) ---
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-d:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d

# --- Production (build from source, gunicorn) ---
prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# --- Deploy (pull from GHCR, gunicorn) ---
deploy:
	docker compose -f docker-compose.deploy.yml -f docker-compose.prod.yml pull
	docker compose -f docker-compose.deploy.yml -f docker-compose.prod.yml up -d

# --- Shared ---
down:
	docker compose down

logs:
	docker compose logs -f propraetor

shell:
	docker compose exec propraetor python manage.py shell

migrate:
	docker compose exec propraetor python manage.py migrate

createsuperuser:
	docker compose exec propraetor python manage.py createsuperuser
