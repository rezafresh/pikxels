setup:
	@poetry lock
	@poetry install --no-root
lint:
	@poetry run black src scripts
	@poetry run isort --profile black src scripts
	@poetry run ruff check src scripts
start-browserless:
	@-docker stop browserless 2> /dev/null
	@docker run --rm -p 33000:3000 --name browserless \
		-e "MAX_CONCURRENT_SESSIONS=5" \
		-e "MAX_QUEUE_LENGTH=5" \
		-e "CONNECTION_TIMEOUT=-1" \
		browserless/chrome
fetch-land-state:
	@poetry run dotenv run \
		python scripts/fetch_land_state.py --land "$${land}" > logs/land-"$${land}"-state.json
serve:
	@poetry run dotenv run \
		uvicorn app.api.asgi:app --host 0.0.0.0 --port 9000 --reload
ngrok:
	@ssh -R 443:localhost:9000 v2@connect.ngrok-agent.com http
create-requirements-file:
	@poetry export --without=dev -o requirements.txt
git-push: create-requirements-file
	@git add .
	@git commit -m "wip"
	@git push