setup:
	@poetry lock
	@poetry install --no-root --with dev
lint:
	@poetry run black src
	@poetry run isort --profile black src
	@poetry run ruff check src
dev:
	@PYTHONPATH=src poetry run python src/app/main.py