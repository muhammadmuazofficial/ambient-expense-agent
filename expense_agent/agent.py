# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Ambient agent that processes expense report emails.

This agent receives expense events via ADK trigger endpoints (Pub/Sub)
and routes them through a graph-based workflow:

- Expenses under $100 are auto-approved immediately.
- Expenses of $100 or more are routed through a security checkpoint (scrubs PII and defends prompt injection).
- Safe expenses are reviewed by the LLM, then paused for human approval.
- Expenses containing prompt injections bypass the LLM and go straight to human approval.
"""

import base64
import json
import re
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import START, Workflow
from pydantic import BaseModel, Field

from .config import config

# ---------------------------------------------------------------------------
# Pydantic schemas for structured data flow between nodes
# ---------------------------------------------------------------------------


class ExpenseData(BaseModel):
    """Expense report data extracted from the incoming email event."""

    amount: float = Field(description="Expense amount in USD")
    submitter: str = Field(description="Email of the person who submitted")
    category: str = Field(description="Expense category, e.g. travel, meals")
    description: str = Field(description="What the expense is for")
    date: str = Field(description="Date of the expense (YYYY-MM-DD)")


# ---------------------------------------------------------------------------
# Function nodes
# ---------------------------------------------------------------------------


def parse_expense_email(node_input: str) -> Event:
    """Parse a Pub/Sub trigger event and extract expense data.

    The trigger endpoint delivers the raw Pub/Sub message JSON. The
    expense payload lives in the ``data`` field, which may be
    base64-encoded (real Pub/Sub) or plain JSON (local testing).
    """
    try:
        event = json.loads(node_input)
    except json.JSONDecodeError:
        return Event(output={"error": f"Invalid JSON: {node_input[:200]}"})

    data = event.get("data")
    if data is None:
        data = event

    if isinstance(data, str):
        try:
            data = json.loads(base64.b64decode(data).decode("utf-8"))
        except Exception:
            return Event(output={"error": f"Failed to decode data: {data[:200]}"})

    return Event(
        output={
            "amount": float(data.get("amount", 0)),
            "submitter": data.get("submitter", "unknown"),
            "category": data.get("category", "other"),
            "description": data.get("description", ""),
            "date": data.get("date", ""),
        }
    )


def route_by_amount(node_input: dict, ctx: Context) -> Event:
    """Route expenses based on the threshold configuration.

    Returns a routing event that the workflow uses to pick the next
    node: ``AUTO_APPROVE`` for amounts under the threshold, ``NEEDS_REVIEW``
    for threshold and above.
    """
    if "error" in node_input:
        return Event(output=node_input, actions={"route": "ERROR"})
    ctx.state["expense_data"] = node_input
    amount = node_input.get("amount", 0.0)
    if amount >= config.review_threshold:
        return Event(output=node_input, actions={"route": "NEEDS_REVIEW"})
    return Event(output=node_input, actions={"route": "AUTO_APPROVE"})


def error_handler(node_input: dict) -> Event:
    """Handle errors gracefully by logging them and returning a status."""
    log_entry = {
        "severity": "ERROR",
        "message": f"Workflow error: {node_input.get('error', 'Unknown error')}",
    }
    print(json.dumps(log_entry), flush=True)
    return Event(output={"status": "error", "error": node_input.get("error", "Unknown error")})


def auto_approve(node_input: dict) -> Event:
    """Auto-approve a low-value expense and log the decision."""
    log_entry = {
        "severity": "INFO",
        "message": (
            f"Expense auto-approved: ${node_input['amount']:.2f}"
            f" from {node_input['submitter']}"
        ),
        "decision": "approved",
        "amount": node_input["amount"],
        "submitter": node_input["submitter"],
        "category": node_input["category"],
    }
    print(json.dumps(log_entry), flush=True)
    return Event(output={"status": "approved", **node_input})


# ---------------------------------------------------------------------------
# Security Checkpoint: PII scrubbing and prompt injection defense
# ---------------------------------------------------------------------------


def security_checkpoint(node_input: dict, ctx: Context) -> Event:
    """Scrubs personal data and checks for prompt injection in the description."""
    description = node_input.get("description", "")

    # 1. PII Scrubbing (SSNs and Credit Cards)
    ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
    cc_pattern = r"\b(?:\d[ -]*?){13,16}\b"

    redacted_categories = set()
    scrubbed_description = description

    if re.search(ssn_pattern, scrubbed_description):
        scrubbed_description = re.sub(
            ssn_pattern, "[REDACTED_SSN]", scrubbed_description
        )
        redacted_categories.add("SSN")

    if re.search(cc_pattern, scrubbed_description):
        scrubbed_description = re.sub(cc_pattern, "[REDACTED_CC]", scrubbed_description)
        redacted_categories.add("Credit Card")

    # Update description in node input and workflow state
    node_input["description"] = scrubbed_description
    ctx.state["expense_data"] = node_input

    if redacted_categories:
        ctx.state["redacted_categories"] = list(redacted_categories)
        log_entry = {
            "severity": "INFO",
            "message": f"PII redacted from description: {list(redacted_categories)}",
            "redacted_categories": list(redacted_categories),
        }
        print(json.dumps(log_entry), flush=True)

    # 2. Prompt Injection Defense
    injection_keywords = [
        "ignore previous",
        "ignore the rules",
        "override",
        "bypass",
        "system prompt",
        "force approve",
        "auto-approve",
        "auto approve",
        "force-approve",
        "you are now",
        "act as",
        "new instruction",
        "change instruction",
        "bypass the rules",
        "force an auto-approval",
    ]

    desc_lower = scrubbed_description.lower()
    has_injection = any(kw in desc_lower for kw in injection_keywords)

    if has_injection:
        ctx.state["security_event"] = True
        log_entry = {
            "severity": "WARNING",
            "message": f"Security alert: Prompt injection detected in description: '{description}'",
            "alert_type": "prompt_injection_detected",
        }
        print(json.dumps(log_entry), flush=True)
        return Event(output=node_input, actions={"route": "NEEDS_HUMAN_DIRECT"})

    return Event(output=node_input, actions={"route": "CLEAN"})


# ---------------------------------------------------------------------------
# LLM review agent (invoked only for expenses >= threshold and clean)
# ---------------------------------------------------------------------------


def emit_expense_alert(
    submitter: str,
    amount: float,
    category: str,
    risk_summary: str,
) -> dict:
    """Emit a structured log alerting finance to review a high-value expense.

    Cloud Run captures JSON stdout as structured logs in Cloud Logging.

    Args:
        submitter: Who submitted the expense.
        amount: The expense amount in USD.
        category: The expense category.
        risk_summary: Why this expense needs review.

    Returns:
        Confirmation that the alert was emitted.
    """
    log_entry = {
        "severity": "WARNING",
        "message": (
            f"Expense review alert: ${amount:.2f} from {submitter} — {risk_summary}"
        ),
        "alert_type": "expense_review",
        "submitter": submitter,
        "amount": amount,
        "category": category,
        "risk_summary": risk_summary,
    }
    print(json.dumps(log_entry), flush=True)
    return {"status": "alert_emitted", "submitter": submitter, "amount": amount}


review_agent = Agent(
    name="review_agent",
    model=config.model,
    mode="single_turn",
    instruction="""You are an expense review agent. You receive expense reports
of $100 or more that need review before approval.

Analyze the expense and:
1. Check for risk factors: unusual category for the amount, vague description,
   suspiciously round numbers, very high value (>$1000), or potential policy
   violations.
2. Call the `emit_expense_alert` tool with the submitter, amount, category,
   and a brief risk summary explaining why this expense needs human review.
3. Return a structured review.

Your review MUST include:
- **Amount**: The expense amount
- **Submitter**: Who submitted it
- **Category**: The expense category
- **Risk level**: low, medium, or high
- **Risk factors**: What flags you found (if any)
- **Recommendation**: approve, request-more-info, or escalate""",
    input_schema=ExpenseData,
    tools=[emit_expense_alert],
)


# ---------------------------------------------------------------------------
# HITL: pause the workflow for human approval
# ---------------------------------------------------------------------------


def request_approval(
    node_input: Any, ctx: Context
) -> AsyncGenerator[RequestInput, None]:
    """Pause the workflow and wait for a human to approve or reject.

    Yields a ``RequestInput`` that the ADK runtime surfaces to the UI.
    """
    expense = ctx.state.get("expense_data", {})

    message = "Expense requires manager approval. Approve or reject."
    if ctx.state.get("security_event"):
        message = "SECURITY WARNING: Prompt injection detected in description. Review with extreme caution! Approve or reject."
    elif ctx.state.get("redacted_categories"):
        redacted = ", ".join(ctx.state["redacted_categories"])
        message = f"Expense requires manager approval (PII Redacted: {redacted}). Approve or reject."

    yield RequestInput(
        message=message,
        payload=expense,
    )


def process_decision(node_input: Any, ctx: Context) -> Event:
    """Process the human's approval decision and log the outcome."""
    decision = "unknown"
    if isinstance(node_input, dict):
        decision = node_input.get("decision", "unknown")
    elif isinstance(node_input, str):
        decision = "approve" if "approve" in node_input.lower() else "reject"

    approved = decision == "approve"
    expense = ctx.state.get("expense_data", {})
    status = "approved" if approved else "rejected"

    severity = "INFO"
    if ctx.state.get("security_event"):
        severity = "WARNING"
    elif not approved:
        severity = "WARNING"

    log_entry = {
        "severity": severity,
        "message": f"Expense {status} by manager",
        "decision": status,
    }
    if ctx.state.get("security_event"):
        log_entry["security_event"] = True
    print(json.dumps(log_entry), flush=True)

    submitter = expense.get("submitter", "unknown")
    amount = expense.get("amount", 0.0)
    category = expense.get("category", "")
    description = expense.get("description", "")
    date = expense.get("date", "")

    parts = [f"${amount:.2f} expense from {submitter} has been {status}."]
    if ctx.state.get("security_event"):
        parts.insert(0, "[SECURITY BLOCKED LLM]")
    if description:
        parts.append(f'"{description}" ({category}) on {date}.')

    if ctx.state.get("redacted_categories"):
        redacted = ", ".join(ctx.state["redacted_categories"])
        parts.append(
            f"(Note: Sensitive personal data [{redacted}] was redacted for security)."
        )

    if approved:
        parts.append(
            "The expense has been logged and will be processed for reimbursement."
        )
    else:
        parts.append(
            "The submitter will be notified and may resubmit with additional documentation."
        )

    return Event(output={"status": status, "message": " ".join(parts)})


# ---------------------------------------------------------------------------
# Graph-based workflow — the root agent
# ---------------------------------------------------------------------------

root_agent = Workflow(
    name="expense_processor",
    edges=[
        (START, parse_expense_email, route_by_amount),
        (
            route_by_amount,
            {
                "AUTO_APPROVE": auto_approve,
                "NEEDS_REVIEW": security_checkpoint,
                "ERROR": error_handler,
            },
        ),
        (
            security_checkpoint,
            {
                "CLEAN": review_agent,
                "NEEDS_HUMAN_DIRECT": request_approval,
            },
        ),
        (review_agent, request_approval, process_decision),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
