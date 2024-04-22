ifneq (,$(wildcard ./.env))
    include .env
    export
endif

setup:
	@poetry lock
	@poetry install --no-root
lint:
	@poetry run black -l 100 src
	@poetry run isort --profile black src
	@poetry run ruff check src
start-api:
	@poetry run python -m src.app.cli.start_api --reload
start-worker:
	@poetry run python -m src.app.cli.start_worker
start-resource-hunter:
	@poetry run python -m src.app.cli.start_resource_hunter
start-rq-info:
	@poetry run rq info -u ${APP_REDIS_URL}
start-rq-dashboard:
	@poetry run rq-dashboard -u ${APP_REDIS_URL}
start-test:
	@poetry run python -m tests.test
ngrok:
	ssh -R 443:localhost:${API_PORT} v2@connect.ngrok-agent.com http
create-requirements-txt:
	@if command -v poetry > /dev/null 2>&1; then \
        poetry export -q --without=dev -o requirements.txt; \
    fi
git-push: lint create-requirements-txt
	@git add .
	@git commit -m wip
	@git push
clean:
	@py3clean .
docker-down:
	@docker compose down
docker-up: docker-down create-requirements-txt
	@docker compose up --build
docker-up-detached: docker-down create-requirements-txt
	@docker compose up -d --build
docker-up-services: docker-down
	@docker compose up browserless redis
docker-redis-flushall:
	@docker compose exec redis \
		redis-cli --no-auth-warning -a ${REDIS_PASSWORD} flushall
docker-redis-cli:
	@docker compose exec redis \
		redis-cli --no-auth-warning -a ${REDIS_PASSWORD}
docker-entry-api:
	@python -m src.app.cli.start_api
docker-entry-worker:
	@python -m src.app.cli.start_worker
docker-start-rq-info:
	@docker compose exec worker rq info -u ${APP_REDIS_URL}
docker-start-resource-hunter:
	@docker compose exec worker \
		python -m src.app.cli.start_resource_hunter
docker-up-standalone-worker: docker-down
	@docker compose up browserless worker
