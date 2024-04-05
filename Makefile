ifneq (,$(wildcard ./.env))
    include .env
    export
endif

WORKER_CONCURRENCY ?= 2
API_PORT ?= 9000
APP_REDIS_HOST ?= localhost
APP_REDIS_PORT ?= 6379

setup:
	@poetry lock
	@poetry install --no-root
lint:
	@poetry run black -l 100 src
	@poetry run isort --profile black src
	@poetry run ruff check src
start-worker:
	@poetry run rq worker-pool \
		-n ${WORKER_CONCURRENCY} \
		-u redis://${APP_REDIS_HOST}:${APP_REDIS_PORT} \
		default \
		low
start-api:
	@poetry run uvicorn src.app.api.asgi:app \
		--host 0.0.0.0 \
		--port ${API_PORT} \
		--reload
start-tree-hunt:
	@poetry run python -m src.app.cli.tree_hunt
ngrok:
	ssh -R 443:localhost:${API_PORT} v2@connect.ngrok-agent.com http
git-push: lint
	@poetry export -q --without=dev -o requirements.txt
	@git add .
	@git commit -m wip
	@git push
docker-down:
	@docker compose down
docker-up: docker-down
	@docker compose up --build
docker-up-detached: docker-down
	@docker compose up -d --build
docker-start-services: docker-down
	@docker compose up browserless redis rq-dashboard
docker-redis-flushall:
	@docker compose exec redis redis-cli flushall
docker-start-standalone-worker: docker-down
	@docker compose up browserless worker --build
docker-entry-api:
	@uvicorn src.app.api.asgi:app --host 0.0.0.0 --port 9000
docker-entry-worker:
	@rq worker-pool \
		-n ${WORKER_CONCURRENCY} \
		-u redis://${APP_REDIS_HOST}:${APP_REDIS_PORT} \
		default \
		low
rq-dashboard:
	@poetry run rq-dashboard \
		-u redis://${APP_REDIS_HOST}:${APP_REDIS_PORT}