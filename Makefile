setup:
	@poetry lock
	@poetry install --no-root
lint:
	@poetry run black src
	@poetry run isort --profile black src
	@poetry run ruff check src
start-fetch-land-state:
	@poetry run dotenv run \
		python -m src.app.cli.fetch_land_state \
			--land "$${land}" > logs/land-"$${land}"-state.json
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
	@rm logs/*.log logs/*.json
docker-down:
	@docker compose down
docker-up: docker-down create-requirements-file
	@docker compose up --build
start-services: docker-down
	@docker compose up browserless
start-load-test:
	@node tests/load-test.js "$${load:-10}"