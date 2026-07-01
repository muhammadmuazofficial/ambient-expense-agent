# Expense Manager Dashboard

This is a standalone manager dashboard service built in FastAPI to manage human-in-the-loop approvals for the Google Cloud Agent Runtime.

## Requirements
Ensure you have the following environment variables configured:
* `GOOGLE_CLOUD_PROJECT`: Your Google Cloud project ID.
* `AGENT_RUNTIME_ID`: The deployed agent's resource name or engine ID on Agent Runtime (e.g. `projects/.../locations/us-east1/reasoningEngines/...`).
* `GOOGLE_CLOUD_LOCATION`: The region of your deployment (defaults to `us-east1`).

## Setup and Run
Use `uv` or standard `pip` to install dependencies and run:

```bash
# Install dependencies
uv pip install -e .

# Run the dashboard service
uv run python main.py
```

Open `http://localhost:8001` in your browser to view the premium dashboard.
