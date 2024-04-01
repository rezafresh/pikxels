setup:
	@poetry lock
	@poetry install --no-root
lint:
	@poetry run black src
	@poetry run isort --profile black src
	@poetry run ruff check src
start-tree-hunt:
	@poetry run dotenv run python -m src.app.cli.tree_hunt
start-api-dev:
	@poetry run dotenv run \
		uvicorn src.app.api.asgi:app --host 0.0.0.0 --port 9000 --reload
ngrok:
	@ssh -R 443:localhost:9000 v2@connect.ngrok-agent.com http
create-requirements-file:
	@poetry export -q --without=dev -o requirements.txt
git-push: lint create-requirements-file
	@git add .
	@git commit -m "$${msg:-wip}"
	@git push
clear-logs:
	@rm logs/*.log
docker-down:
	@docker compose down
docker-up: docker-down create-requirements-file
	@docker compose up --build
start-services: docker-down
	@docker compose up browserless redis
start-load-test:
	@node tests/load-test.js "$${load:-10}"
start-rq-worker:
	@poetry run dotenv run rq worker-pool -n "$${workers:-1}" > logs/rq-worker.log
redis-cli:
	@docker compose exec redis redis-cli
redis-flushall:
	@docker compose exec redis redis-cli flushall
rq-queue-empty:
	@poetry run rq empty default