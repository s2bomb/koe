.PHONY: lint typecheck test run

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run pyright

test:
	uv run pytest tests/

run:
	uv run koe
