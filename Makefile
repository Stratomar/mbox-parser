.PHONY: format lint typecheck test check

format:
	.venv/bin/ruff format src/ tests/

lint:
	.venv/bin/ruff check src/ tests/

typecheck:
	.venv/bin/mypy src/

test:
	.venv/bin/pytest

check: format lint typecheck test
