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
	@poetry run uvicorn src.app.api.asgi:app \
		--host 0.0.0.0 \
		--port ${API_PORT} \
		--reload
ngrok:
	ssh -R 443:localhost:${API_PORT} v2@connect.ngrok-agent.com http
git-push: lint
	@poetry export -q --without=dev -o requirements.txt
	@git add .
	@git commit -m wip
	@git push
clean:
	@py3clean .
docker-down:
	@docker compose down
docker-up: docker-down
	@docker compose up --build
docker-up-detached: docker-down
	@docker compose up -d --build
docker-up-services: docker-down
	@docker compose up browserless redis
docker-redis-flushall:
	@docker compose exec redis redis-cli flushall
docker-entry-api:
	@uvicorn src.app.api.asgi:app --host 0.0.0.0 --port 9000