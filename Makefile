.PHONY: install playground run

install:
	agents-cli install

playground:
	uv run adk web "." --host 127.0.0.1 --port 8080 --allow_origins "*"

run:
	uv run python -m expense_agent.fast_api_app
