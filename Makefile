.PHONY: install playground run generate-traces grade

install:
	agents-cli install

playground:
	uv run adk web "." --host 127.0.0.1 --port 8080 --allow_origins "*"

run:
	uv run python -m expense_agent.fast_api_app

generate-traces:
	uv run python tests/eval/generate_traces.py

grade:
	uv run python tests/eval/grade_traces.py
