setup:
	@poetry lock
	@poetry install --no-root
lint:
	@poetry run black src
	@poetry run isort --profile black src
	@poetry run ruff check src
start-tree-hunt:
	@poetry run dotenv run python -m src.app.cli.tree_hunt
start-api:
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
docker-down:
	@docker compose down
docker-up: docker-down create-requirements-file
	@docker compose up --build
start-services: docker-down
	@docker compose up browserless redis worker
start-load-test:
	@node tests/load-test.js "$${load:-10}"
start-worker:
	@poetry run dotenv run rq worker-pool -n "$${workers:-1}" > logs/rq-worker.log
redis-flushall:
	@docker compose exec redis redis-cli flushall
docker-start-standalone-worker:
	@docker compose down browserless worker
	@docker compose up browserless worker
docker-entry-api:
	@uvicorn src.app.api.asgi:app --host 0.0.0.0 --port 9000
docker-entry-worker:
	rq worker-pool -n "$${workers:-1}"
rq-dashboard:
	@poetry run rq-dashboard