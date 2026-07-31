.PHONY: help build up dev down restart logs logs-backend logs-db ps migrate makemigrations shell test check createsuperuser clean

help:
	@echo "Jira Import Backend commands:"
	@echo ""
	@echo "  make build          Build Docker images"
	@echo "  make up             Start services in background"
	@echo "  make dev            Build and start services in foreground"
	@echo "  make down           Stop services"
	@echo "  make restart        Restart services"
	@echo "  make logs           Show logs for all services"
	@echo "  make logs-backend   Show django + celery logs"
	@echo "  make logs-db        Show database logs"
	@echo "  make ps             Show containers status"
	@echo "  make migrate        Run migrations inside django container"
	@echo "  make makemigrations Create migrations inside django container"
	@echo "  make shell          Open Django shell inside django container"
	@echo "  make test           Run pytest inside django container"
	@echo "  make check          Run Django system check inside django container"
	@echo "  make createsuperuser Create Django superuser"
	@echo "  make clean          Stop services and remove volumes"

build:
	docker compose build

up:
	docker compose up -d

dev:
	docker compose up --build

down:
	docker compose down

restart:
	docker compose down
	docker compose up -d

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f django celery

logs-db:
	docker compose logs -f db

ps:
	docker compose ps

migrate:
	docker compose exec django python manage.py migrate

makemigrations:
	docker compose exec django python manage.py makemigrations

shell:
	docker compose exec django python manage.py shell

test:
	docker compose exec django pytest -q

check:
	docker compose exec django python manage.py check

createsuperuser:
	docker compose exec django python manage.py createsuperuser

clean:
	docker compose down -v
