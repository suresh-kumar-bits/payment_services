# Makefile for Payment Service

.PHONY: help build up down restart logs shell test clean setup migrate health

# Variables
SERVICE_NAME = payment-service
DOCKER_COMPOSE = docker-compose
PYTHON = python3
PIP = pip3

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m # No Color

## Help
help:
	@echo "$(GREEN)Payment Service - Makefile Commands$(NC)"
	@echo "$(YELLOW)========================================$(NC)"
	@echo "Development:"
	@echo "  make setup        - Initial setup (install dependencies, create network)"
	@echo "  make build        - Build Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - View service logs"
	@echo "  make shell        - Access payment API container shell"
	@echo ""
	@echo "Database:"
	@echo "  make db-setup     - Run database setup script"
	@echo "  make db-shell     - Access PostgreSQL shell"
	@echo "  make db-backup    - Backup database"
	@echo "  make db-restore   - Restore database from backup"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run tests"
	@echo "  make test-api     - Test API endpoints"
	@echo "  make health       - Check service health"
	@echo ""
	@echo "Deployment:"
	@echo "  make k8s-deploy   - Deploy to Kubernetes"
	@echo "  make k8s-delete   - Remove from Kubernetes"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Clean up containers and volumes"
	@echo "  make prune        - Remove all unused Docker resources"

## Initial setup
setup:
	@echo "$(GREEN)Setting up Payment Service...$(NC)"
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)Creating Docker network...$(NC)"
	-docker network create ride-hailing-network
	@echo "$(GREEN)Setup complete!$(NC)"

## Build Docker images
build:
	@echo "$(GREEN)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build

## Start services
up:
	@echo "$(GREEN)Starting services...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Waiting for services to be ready...$(NC)"
	@sleep 5
	@make health

## Stop services
down:
	@echo "$(YELLOW)Stopping services...$(NC)"
	$(DOCKER_COMPOSE) down

## Restart services
restart:
	@echo "$(YELLOW)Restarting services...$(NC)"
	$(DOCKER_COMPOSE) restart

## View logs
logs:
	$(DOCKER_COMPOSE) logs -f payment_api

## Access payment API container shell
shell:
	$(DOCKER_COMPOSE) exec payment_api /bin/sh

## Database setup
db-setup:
	@echo "$(GREEN)Setting up database...$(NC)"
	$(DOCKER_COMPOSE) exec payment_api python database_setup.py

## Access PostgreSQL shell
db-shell:
	$(DOCKER_COMPOSE) exec payment_db psql -U postgres -d postgres

## Backup database
db-backup:
	@echo "$(GREEN)Backing up database...$(NC)"
	@mkdir -p backups
	$(DOCKER_COMPOSE) exec payment_db pg_dump -U postgres postgres > backups/payment_db_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backed up to backups/$(NC)"

## Restore database
db-restore:
	@echo "$(YELLOW)Restoring database from latest backup...$(NC)"
	@latest_backup=$$(ls -t backups/*.sql | head -1); \
	if [ -z "$$latest_backup" ]; then \
		echo "$(RED)No backup found!$(NC)"; \
	else \
		cat $$latest_backup | $(DOCKER_COMPOSE) exec -T payment_db psql -U postgres postgres; \
		echo "$(GREEN)Database restored from $$latest_backup$(NC)"; \
	fi

## Run tests
test:
	@echo "$(GREEN)Running tests...$(NC)"
	$(DOCKER_COMPOSE) exec payment_api pytest tests/ -v

## Test API endpoints
test-api:
	@echo "$(GREEN)Testing API endpoints...$(NC)"
	@echo "$(YELLOW)1. Health Check:$(NC)"
	curl -s http://localhost:8082/health | json_pp
	@echo "\n$(YELLOW)2. Get Payments:$(NC)"
	curl -s http://localhost:8082/v1/payments?limit=5 | json_pp
	@echo "\n$(YELLOW)3. Test Charge (Idempotent):$(NC)"
	curl -s -X POST http://localhost:8082/v1/payments/charge \
		-H "Content-Type: application/json" \
		-d '{"idempotency_key":"test-$(shell date +%s)","trip_id":1,"method":"CARD"}' | json_pp

## Check service health
health:
	@echo "$(GREEN)Checking service health...$(NC)"
	@response=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8082/health); \
	if [ "$$response" = "200" ]; then \
		echo "$(GREEN)✓ Payment Service is healthy$(NC)"; \
		curl -s http://localhost:8082/health | json_pp; \
	else \
		echo "$(RED)✗ Payment Service is not responding (HTTP $$response)$(NC)"; \
		exit 1; \
	fi

## Deploy to Kubernetes
k8s-deploy:
	@echo "$(GREEN)Deploying to Kubernetes...$(NC)"
	kubectl apply -f k8s/

## Remove from Kubernetes
k8s-delete:
	@echo "$(YELLOW)Removing from Kubernetes...$(NC)"
	kubectl delete -f k8s/

## Clean up containers and volumes
clean:
	@echo "$(YELLOW)Cleaning up...$(NC)"
	$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)Cleanup complete!$(NC)"

## Remove all unused Docker resources
prune:
	@echo "$(RED)Removing all unused Docker resources...$(NC)"
	docker system prune -af
	docker volume prune -f

## Monitor logs in real-time
monitor:
	@echo "$(GREEN)Monitoring Payment Service logs...$(NC)"
	$(DOCKER_COMPOSE) logs -f payment_api payment_db

## Generate API documentation
docs:
	@echo "$(GREEN)Generating API documentation...$(NC)"
	@echo "API documentation will be available at http://localhost:8082/apidocs"

## Run development server locally
dev:
	@echo "$(GREEN)Starting development server...$(NC)"
	$(PYTHON) app.py

## Format code
format:
	@echo "$(GREEN)Formatting code...$(NC)"
	black *.py
	isort *.py

## Lint code
lint:
	@echo "$(GREEN)Linting code...$(NC)"
	flake8 *.py
	pylint *.py