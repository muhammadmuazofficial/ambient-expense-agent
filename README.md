# 💸 Ambient Expense Approval Agent (ADK 2.0 Graph Workflow)

An ambient, event-driven web service that automates expense report reviews, sanitizes inputs, and routes approval decisions using the new **Google Agent Development Kit (ADK 2.0) Graph Workflow API** and **FastAPI**.
Designed to run locally or deploy directly to serverless runtimes (like Google Cloud Run), the agent processes incoming expense notifications via Google Cloud Pub/Sub push triggers

## 🚀 Key Features
*   **Graph Workflow Topology:** Built using ADK 2.0's function-node graph architecture with structured edge routing.
*   **Intelligent Auto-Routing:**
    *   **Under $100:** Auto-approved instantly with zero LLM costs.
    *   **$100 or more:** Promoted to security checks, LLM evaluation, and human-in-the-loop manager approval.
*   **Robust Security Checkpoint:**
    *   **PII Scrubbing:** Automatically detects and redacts sensitive data (SSNs and Credit Cards) before it reaches the LLM or logs.
    *   **Prompt Injection Defense:** Defends against malicious override attempts (e.g., instructions attempting to force auto-approval). If detected, it bypasses the LLM entirely and flags a prominent security warning to the human reviewer.
*   **LLM Risk Assessment:** Evaluates high-value expenses using `gemini-3.1-flash-lite` to detect potential policy violations or risk factors.
*   **Human-in-the-Loop (HITL):** Seamlessly pauses execution using ADK's `RequestInput` mechanism, waiting for manager decisions with warnings for security threats or redacted PII.
*   **Ambient Web Service:** FastAPI web service serving on port `8080` with built-in Pub/Sub envelope normalization middleware and standard Python structured logging.

## 🛠️ Architecture
```mermaid
graph TD
    Start([Pub/Sub Event]) --> Parse[Parse Expense Email]
    Parse --> Route{Amount Check}
    
    Route -- "< $100" --> AutoApprove[Auto Approve Node]
    Route -- ">= $100" --> SecurityCheck[Security Checkpoint]
    
    SecurityCheck -- "Clean" --> LLMReview[Gemini LLM Risk Review]
    SecurityCheck -- "Prompt Injection Detected" --> HITL[Human-in-the-Loop Approval]
    
    LLMReview --> HITL
    HITL --> Decision[Process Decision]
    
    AutoApprove --> End([End Workflow])
    Decision --> End```
    
## Project Structure

ambient-expense-agent/
├── app/         # Core agent code
│   ├── agent.py               # Main agent logic
│   └── app_utils/             # App utilities and helpers
├── tests/                     # Unit, integration, and load tests
├── GEMINI.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

> 💡 **Tip:** Use [Gemini CLI](https://github.com/google-gemini/gemini-cli) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
```

Install required packages:

```bash
agents-cli install
```

Test the agent with a local web server:

```bash
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        |

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

---

## Development

Edit your agent logic in `app/agent.py` and test with `agents-cli playground` - it auto-reloads on save.

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up your production infrastructure, run `agents-cli infra cicd`.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.
