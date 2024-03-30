setup:
	@poetry lock
	@poetry install --no-root
lint:
	@poetry run black src
	@poetry run isort --profile black src
	@poetry run ruff check src
start-browserless:
	@docker compose down browserless
	@docker compose up browserless -d
fetch-land-state:
	@poetry run dotenv run \
		python -m src.app.cli.fetch_land_state --land "$${land}" > logs/land-"$${land}"-state.json
serve:
	@poetry run dotenv run \
		uvicorn src.app.api.asgi:app --host 0.0.0.0 --port 9000 --reload
ngrok:
	@ssh -R 443:localhost:9000 v2@connect.ngrok-agent.com http
create-requirements-file:
	@poetry export --without=dev -o requirements.txt
git-push: create-requirements-file lint
	@git add .
	@git commit -m "wip"
	@git push
clear-logs:
	@rm logs/*.log logs/*.json
start: create-requirements-file
	@docker compose up --build -d