include .env
export

setup:
	@poetry lock
	@poetry install --no-root
clean:
	@py3clean .
lint: clean
	@poetry run black -l 100 src
	@poetry run isort --profile black src
	@poetry run ruff check src
create-requirements-txt:
	@if command -v poetry > /dev/null 2>&1; then \
        poetry export -q --without=dev -o requirements.txt; \
    fi
ngrok:
	ssh -R 443:localhost:${API_PORT} v2@connect.ngrok-agent.com http
git-commit: lint create-requirements-txt
	@git add .
	@git commit -m wip
	@git push
git-push-main:
	@git rebase dev main
	@git push
	@git switch dev
ghcr-push-image: create-requirements-txt
	@docker build -t pikxels:latest .
	@docker tag pikxels:latest ghcr.io/pikxels/pikxels:latest
	@docker push ghcr.io/pikxels/pikxels:latest
start-docker-services: docker-down
	@docker compose up browserless redis
start-api:
	@poetry run python -m src.app.cli.start_api --reload
start-resource-hunter:
	@poetry run python -m src.app.cli.start_resource_hunter
start-rq-info:
	@poetry run rq info -u ${APP_REDIS_URL}
start-rq-dashboard:
	@poetry run rq-dashboard -u ${APP_REDIS_URL}
start-test:
	@poetry run python -m tests.test
docker-down:
	@docker compose down
docker-up: docker-down create-requirements-txt
	@docker compose up -d --build
docker-redis-flushall:
	@docker compose exec redis \
		redis-cli --no-auth-warning -a ${REDIS_PASSWORD} flushall
docker-rq-info:
	@docker compose exec resource-hunter rq info -u ${APP_REDIS_URL}
docker-entry-api:
	@python -m src.app.cli.start_api
docker-entry-resource-hunter:
	@python -m src.app.cli.start_resource_hunter
docker-entry-worker:
	@python -m src.app.cli.start_worker
