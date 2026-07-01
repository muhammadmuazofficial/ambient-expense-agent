import os
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import vertexai
from google.adk.sessions import VertexAiSessionService
from vertexai.preview.reasoning_engines import ReasoningEngine
from google.cloud.aiplatform_v1beta1 import types as aip_types
from vertexai.reasoning_engines import _utils

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manager-dashboard")

app = FastAPI(title="Expense Agent Manager Dashboard")

# Read Environment Configuration
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
agent_runtime_id = os.environ.get("AGENT_RUNTIME_ID")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-east1")

if not project_id:
    logger.error("Missing GOOGLE_CLOUD_PROJECT environment variable.")
if not agent_runtime_id:
    logger.error("Missing AGENT_RUNTIME_ID environment variable.")

# Initialize Vertex AI
if project_id and agent_runtime_id:
    logger.info(f"Initializing Vertex AI. Project: {project_id}, Region: {location}, Engine ID: {agent_runtime_id}")
    vertexai.init(project=project_id, location=location)
    
    # Extract short engine ID for VertexAiSessionService if needed
    short_engine_id = agent_runtime_id.split("/")[-1] if "/" in agent_runtime_id else agent_runtime_id
    
    session_service = VertexAiSessionService(
        project=project_id,
        location=location,
        agent_engine_id=short_engine_id
    )
else:
    session_service = None
    logger.warning("Vertex AI session service could not be initialized due to missing environment variables.")


class ActionRequest(BaseModel):
    interrupt_id: str
    approved: bool


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serves the premium, responsive dashboard page."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expense Agent - Manager Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0B0A0F;
            --card-bg: rgba(255, 255, 255, 0.03);
            --card-border: rgba(255, 255, 255, 0.08);
            --text-color: #F3F4F6;
            --text-muted: #9CA3AF;
            --primary: #8B5CF6;
            --primary-glow: rgba(139, 92, 246, 0.15);
            --success: #10B981;
            --success-glow: rgba(16, 185, 129, 0.2);
            --danger: #EF4444;
            --danger-glow: rgba(239, 68, 68, 0.2);
            --warning: #F59E0B;
            --warning-glow: rgba(245, 158, 11, 0.2);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            min-height: 100vh;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(139, 92, 246, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 40%);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 3rem;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 1.5rem;
        }

        .logo-section h1 {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #A78BFA 0%, #34D399 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.25rem;
        }

        .logo-section p {
            color: var(--text-muted);
            font-size: 0.875rem;
        }

        .refresh-btn {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            color: var(--text-color);
            padding: 0.6rem 1.2rem;
            border-radius: 9999px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s ease;
            backdrop-filter: blur(12px);
        }

        .refresh-btn:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
        }

        /* Dashboard Grid */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 2rem;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary) 0%, transparent 100%);
            opacity: 0.5;
        }

        .card.security-warning::before {
            background: linear-gradient(90deg, var(--warning) 0%, transparent 100%);
        }

        .card:hover {
            transform: translateY(-5px);
            border-color: rgba(139, 92, 246, 0.3);
            box-shadow: 0 10px 30px var(--primary-glow);
        }

        .card.security-warning:hover {
            border-color: rgba(245, 158, 11, 0.3);
            box-shadow: 0 10px 30px var(--warning-glow);
        }

        /* Card Elements */
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }

        .amount {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-color);
        }

        .badge {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            text-transform: uppercase;
        }

        .badge-pending {
            background: var(--primary-glow);
            color: #A78BFA;
            border: 1px solid rgba(167, 139, 250, 0.3);
        }

        .badge-warning {
            background: var(--warning-glow);
            color: #FBBF24;
            border: 1px solid rgba(251, 191, 36, 0.3);
        }

        .card-body {
            margin-bottom: 1.5rem;
            flex-grow: 1;
        }

        .detail-row {
            display: flex;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
        }

        .detail-label {
            color: var(--text-muted);
            width: 100px;
            flex-shrink: 0;
        }

        .detail-value {
            color: var(--text-color);
            font-weight: 500;
            word-break: break-all;
        }

        .alert-message {
            margin-top: 1rem;
            padding: 0.75rem;
            background: rgba(245, 158, 11, 0.05);
            border: 1px solid rgba(245, 158, 11, 0.15);
            border-radius: 8px;
            font-size: 0.85rem;
            color: #FBBF24;
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }

        .card-actions {
            display: flex;
            gap: 1rem;
            margin-top: auto;
        }

        .btn {
            flex: 1;
            padding: 0.75rem;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .btn-approve {
            background: var(--success);
            color: #fff;
        }

        .btn-approve:hover {
            background: #059669;
            box-shadow: 0 4px 12px var(--success-glow);
        }

        .btn-reject {
            background: var(--danger);
            color: #fff;
        }

        .btn-reject:hover {
            background: #DC2626;
            box-shadow: 0 4px 12px var(--danger-glow);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Spinner */
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 0.8s linear infinite;
            display: none;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Empty State */
        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 5rem 2rem;
            background: var(--card-bg);
            border: 1px dashed var(--card-border);
            border-radius: 16px;
            backdrop-filter: blur(12px);
        }

        .empty-state h3 {
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
            color: var(--text-color);
        }

        .empty-state p {
            color: var(--text-muted);
        }

        /* Modal styling - Slide out from right */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        }

        .modal-overlay.active {
            opacity: 1;
            visibility: visible;
        }

        .modal-content {
            position: fixed;
            top: 0;
            right: -450px;
            width: 450px;
            max-width: 100vw;
            height: 100vh;
            background: #111019;
            border-left: 1px solid var(--card-border);
            padding: 2.5rem;
            box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
            z-index: 1001;
            transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .modal-overlay.active + .modal-content {
            right: 0;
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
        }

        .modal-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-color);
        }

        .close-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            cursor: pointer;
            transition: color 0.2s;
        }

        .close-btn:hover {
            color: var(--text-color);
        }

        .modal-body {
            flex-grow: 1;
            overflow-y: auto;
            margin-bottom: 2rem;
        }

        .review-status-box {
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-weight: 600;
        }

        .review-status-box.approved {
            background: var(--success-glow);
            color: #34D399;
            border: 1px solid rgba(52, 211, 153, 0.3);
        }

        .review-status-box.rejected {
            background: var(--danger-glow);
            color: #F87171;
            border: 1px solid rgba(248, 113, 113, 0.3);
        }

        .review-text-title {
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            letter-spacing: 0.05em;
        }

        .review-text {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 1.25rem;
            font-size: 0.95rem;
            line-height: 1.6;
            color: #E5E7EB;
            white-space: pre-wrap;
        }

        .modal-footer {
            margin-top: auto;
        }

        .btn-modal-close {
            width: 100%;
            background: var(--primary);
            color: white;
            padding: 0.85rem;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-modal-close:hover {
            background: #7C3AED;
            box-shadow: 0 4px 12px var(--primary-glow);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section">
                <h1>Expense Manager</h1>
                <p>Gemini Enterprise Agent Approval Portal</p>
            </div>
            <button class="refresh-btn" onclick="fetchPendingApprovals()">Refresh Dashboard</button>
        </header>

        <main>
            <div class="dashboard-grid" id="dashboard">
                <!-- Loading State -->
                <div class="empty-state" id="loading-state">
                    <h3>Scanning Agent Sessions...</h3>
                    <p>Loading unresolved manager approval steps from Agent Runtime</p>
                </div>
            </div>
        </main>
    </div>

    <!-- Modal Elements -->
    <div class="modal-overlay" id="modal-overlay" onclick="closeModal()"></div>
    <div class="modal-content" id="modal-content">
        <div>
            <div class="modal-header">
                <h3 class="modal-title">Compliance Review</h3>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="review-status-box" id="review-status-box">
                    <!-- Status dynamic -->
                </div>
                <div class="review-text-title">Agent Response Message</div>
                <div class="review-text" id="review-text">
                    <!-- Text dynamic -->
                </div>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn-modal-close" onclick="closeModal()">Acknowledge</button>
        </div>
    </div>

    <script>
        async function fetchPendingApprovals() {
            const dashboard = document.getElementById('dashboard');
            dashboard.innerHTML = `
                <div class="empty-state">
                    <h3>Scanning Agent Sessions...</h3>
                    <p>Loading unresolved manager approval steps from Agent Runtime</p>
                </div>
            `;

            try {
                const response = await fetch('/api/pending');
                if (!response.ok) throw new Error('Failed to fetch pending approvals');
                const data = await response.json();
                
                if (data.length === 0) {
                    dashboard.innerHTML = `
                        <div class="empty-state">
                            <h3>All Caught Up!</h3>
                            <p>No expense reports are currently waiting for manager approval.</p>
                        </div>
                    `;
                    return;
                }

                dashboard.innerHTML = '';
                data.forEach(item => {
                    const isSecurityWarning = item.message && item.message.includes('SECURITY');
                    const card = document.createElement('div');
                    card.className = `card \${isSecurityWarning ? 'security-warning' : ''}`;
                    
                    const timestampStr = new Date(item.timestamp * 1000).toLocaleString();

                    card.innerHTML = `
                        <div>
                            <div class="card-header">
                                <span class="amount">$\${parseFloat(item.expense.amount || 0).toFixed(2)}</span>
                                <span class="badge \${isSecurityWarning ? 'badge-warning' : 'badge-pending'}">
                                    \${isSecurityWarning ? 'Security Alert' : 'Pending'}
                                </span>
                            </div>
                            <div class="card-body">
                                <div class="detail-row">
                                    <span class="detail-label">Submitter</span>
                                    <span class="detail-value">\${escapeHtml(item.expense.submitter || 'Unknown')}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Category</span>
                                    <span class="detail-value">\${escapeHtml(item.expense.category || 'Unknown')}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Description</span>
                                    <span class="detail-value">\${escapeHtml(item.expense.description || 'No description provided')}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Date</span>
                                    <span class="detail-value">\${escapeHtml(item.expense.date || 'N/A')}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="detail-label">Detected</span>
                                    <span class="detail-value">\${timestampStr}</span>
                                </div>
                                \${isSecurityWarning ? `
                                    <div class="alert-message">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                                            <line x1="12" y1="9" x2="12" y2="13"></line>
                                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                                        </svg>
                                        <span>\${escapeHtml(item.message)}</span>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                        <div class="card-actions">
                            <button class="btn btn-approve" onclick="takeAction('\${item.session_id}', '\${item.interrupt_id}', true, this)">
                                <span class="spinner"></span>
                                <span class="btn-text">Approve</span>
                            </button>
                            <button class="btn btn-reject" onclick="takeAction('\${item.session_id}', '\${item.interrupt_id}', false, this)">
                                <span class="spinner"></span>
                                <span class="btn-text">Reject</span>
                            </button>
                        </div>
                    `;
                    dashboard.appendChild(card);
                });
            } catch (err) {
                dashboard.innerHTML = `
                    <div class="empty-state">
                        <h3 style="color: var(--danger);">Dashboard Error</h3>
                        <p>\${escapeHtml(err.message)}</p>
                    </div>
                `;
            }
        }

        async function takeAction(sessionId, interruptId, approved, btnElement) {
            // Disable all buttons in the card
            const card = btnElement.closest('.card');
            const buttons = card.querySelectorAll('.btn');
            buttons.forEach(btn => btn.disabled = true);
            
            // Show spinner on the clicked button
            const spinner = btnElement.querySelector('.spinner');
            const btnText = btnElement.querySelector('.btn-text');
            if (spinner) spinner.style.display = 'inline-block';
            if (btnText) btnText.style.display = 'none';

            try {
                const response = await fetch(`/api/action/\${sessionId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        interrupt_id: interruptId,
                        approved: approved
                    })
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.detail || 'Action execution failed');
                }

                const result = await response.json();
                
                // Show modal with the final compliance review
                showModal(approved, result.message || 'The session was resumed successfully, but no outcome message was returned.');
                
                // Refresh dashboard list
                await fetchPendingApprovals();
            } catch (err) {
                alert(`Error executing action: \${err.message}`);
                // Re-enable buttons on error
                buttons.forEach(btn => btn.disabled = false);
                if (spinner) spinner.style.display = 'none';
                if (btnText) btnText.style.display = 'inline-block';
            }
        }

        function showModal(approved, message) {
            const overlay = document.getElementById('modal-overlay');
            const content = document.getElementById('modal-content');
            const statusBox = document.getElementById('review-status-box');
            const reviewText = document.getElementById('review-text');

            statusBox.className = `review-status-box \${approved ? 'approved' : 'rejected'}`;
            statusBox.innerHTML = approved ? `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span>Approved & Logged</span>
            ` : `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
                <span>Rejected & Blocked</span>
            `;

            reviewText.textContent = message;
            overlay.classList.add('active');
        }

        function closeModal() {
            const overlay = document.getElementById('modal-overlay');
            overlay.classList.remove('active');
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.toString()
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        // Initialize dashboard on load
        window.addEventListener('load', fetchPendingApprovals);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/api/pending")
async def get_pending_approvals():
    """Queries Agent Runtime sessions and parses outstanding HITL requests."""
    if not session_service:
        raise HTTPException(
            status_code=500,
            detail="Vertex AI Session Service is not initialized. Check your environment variables."
        )

    try:
        # Enumerate sessions under the 'default-user' scope
        logger.info("Listing sessions for default-user...")
        list_resp = await session_service.list_sessions(app_name="app", user_id="default-user")
        
        pending_list = []
        for sess in list_resp.sessions:
            logger.info(f"Retrieving session events for session: {sess.id}")
            full_session = await session_service.get_session(
                app_name="app",
                user_id="default-user",
                session_id=sess.id
            )
            
            # Map unresolved function call events
            calls = {}
            for ev in full_session.events:
                if ev.content and ev.content.parts:
                    for part in ev.content.parts:
                        # Identify hitl trigger
                        if part.function_call and part.function_call.name == "adk_request_input":
                            calls[part.function_call.id] = (ev, part.function_call)
                        # Identify hitl response
                        if part.function_response and part.function_response.name == "adk_request_input":
                            calls.pop(part.function_response.id, None)

            # Package remaining unresolved calls
            for interrupt_id, (ev, call) in calls.items():
                expense_payload = call.args.get("payload") or {}
                message_text = call.args.get("message") or "Manager review required."
                pending_list.append({
                    "session_id": sess.id,
                    "interrupt_id": interrupt_id,
                    "expense": expense_payload,
                    "message": message_text,
                    "timestamp": ev.timestamp
                })
        
        # Sort by timestamp descending (newest first)
        pending_list.sort(key=lambda x: x["timestamp"], reverse=True)
        return pending_list

    except Exception as e:
        logger.exception("Failed to query pending sessions.")
        raise HTTPException(status_code=500, detail=f"Error querying Agent Runtime: {str(e)}")


@app.post("/api/action/{session_id}")
async def post_action(session_id: str, action: ActionRequest):
    """Resumes the paused Reasoning Engine session by passing the response payload."""
    if not project_id or not agent_runtime_id:
        raise HTTPException(
            status_code=500,
            detail="Service environment is not configured. Missing PROJECT or RUNTIME ID."
        )

    try:
        # Load the deployed Reasoning Engine client
        logger.info(f"Loading reasoning engine: {agent_runtime_id}")
        re = ReasoningEngine(agent_runtime_id)
        
        # Prepare the resume payload.
        # Pass both "approved" (requested by user) and "decision" (expected by agent)
        decision_val = "approve" if action.approved else "reject"
        resume_payload = {
            "role": "user",
            "parts": [
                {
                    "function_response": {
                        "id": action.interrupt_id,
                        "name": "adk_request_input",
                        "response": {
                            "approved": action.approved,
                            "decision": decision_val
                        }
                    }
                }
            ]
        }

        # Structure input parameters for the stream_query execution
        input_data = {
            "message": resume_payload,
            "user_id": "default-user",
            "session_id": session_id
        }

        logger.info(f"Resuming session {session_id} using stream_query...")
        response_stream = re.execution_api_client.stream_query_reasoning_engine(
            request=aip_types.StreamQueryReasoningEngineRequest(
                name=re.resource_name,
                input=input_data,
                class_method="stream_query"
            )
        )

        # Consume the event stream
        events = []
        for chunk in response_stream:
            for parsed_json in _utils.yield_parsed_json(chunk):
                if parsed_json is not None:
                    events.append(parsed_json)

        # Parse outcome message from process_decision node output
        outcome_message = "Resumed successfully."
        for event in reversed(events):
            output = event.get("output")
            if isinstance(output, dict) and "message" in output:
                outcome_message = output["message"]
                break

        return {"status": "success", "message": outcome_message}

    except Exception as e:
        logger.exception(f"Failed to execute action on session {session_id}.")
        raise HTTPException(status_code=500, detail=f"Failed to resume session: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
