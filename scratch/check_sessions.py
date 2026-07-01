import asyncio
import vertexai
import os
import json
from google.adk.sessions import VertexAiSessionService

async def main():
    vertexai.init(project="gen-lang-client-0695440299", location="us-east1")
    s = VertexAiSessionService(
        project="gen-lang-client-0695440299",
        location="us-east1",
        agent_engine_id="9076547652128079872"
    )
    sess_full = await s.get_session(app_name="app", user_id="vais-query-reasoning-engine", session_id="87517277280272384")
    for idx, ev in enumerate(sess_full.events):
        print(f"\n--- Event {idx} ---")
        print(json.dumps(ev.model_dump(exclude_none=True, mode="json"), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
