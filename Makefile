ifneq (,$(wildcard ./.env))
    include .env
    export
endif

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
git-push: lint create-requirements-txt
	@git add .
	@git commit -m wip
	@git push
git-update-main:
	@git rebase dev main
	@git push
	@git switch dev
ghcr-push-image: create-requirements-txt
	@docker build -t pikxels:"$${TAG:-dev}" .
	@docker tag pikxels:"$${TAG:-dev}" ghcr.io/pikxels/pikxels:"$${TAG:-dev}"
	@docker push ghcr.io/pikxels/pikxels:"$${TAG:-dev}"
git-push-publish: git-push ghcr-push-image
	@echo "Git push and image publish completed"
start-docker-services: docker-down
	@docker compose up browserless redis
start-rq-info:
	@poetry run rq info -u ${APP_REDIS_URL}
start-worker:
	@poetry run python -m src.app.cli.start_worker
start-resource-hunter:
	@poetry run python -m src.app.cli.start_resource_hunter
start-api:
	@poetry run python -m src.app.cli.start_api --reload
docker-down:
	@docker compose down
docker-up: docker-down create-requirements-txt
	@docker compose up --build
docker-up-detached: docker-down create-requirements-txt
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
docker-entry-discord-bot:
	@python -m src.app.cli.start_discord_bot
