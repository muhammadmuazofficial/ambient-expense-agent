import os
import json
import base64
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from expense_agent.agent import root_agent

def to_dict(obj):
    """Recursively convert Pydantic models / GenAI SDK models and bytes to plain dicts/JSON."""
    if hasattr(obj, "model_dump"):
        return to_dict(obj.model_dump(exclude_none=True))
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj

def run_scenario(case_id, trigger_payload):
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="eval_user", app_name="expense_agent")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="expense_agent")

    # Construct the initial user trigger message
    message = types.Content(role="user", parts=[types.Part.from_text(text=trigger_payload)])
    
    turns = []
    
    # --- Turn 0 ---
    events_turn_0 = []
    events_turn_0.append({
        "author": "user",
        "content": to_dict(message)
    })
    
    runner_events = list(runner.run(new_message=message, user_id="eval_user", session_id=session.id))
    
    interrupt_id = None
    is_injection = "ignore previous" in trigger_payload.lower() or "override" in trigger_payload.lower()
    
    for event in runner_events:
        if event.content:
            # Check if this event contains the human-in-the-loop request
            for part in event.content.parts:
                if part.function_call and part.function_call.name == "adk_request_input":
                    interrupt_id = part.function_call.id
            
            # Determine author: tool if function response, else agent
            is_tool = any(p.function_response for p in event.content.parts)
            author = "tool" if is_tool else "expense_processor"
            
            events_turn_0.append({
                "author": author,
                "content": to_dict(event.content)
            })
            
    turns.append({
        "turn_index": 0,
        "events": events_turn_0
    })
    
    # --- Turn 1 (if human-in-the-loop suspended the execution) ---
    if interrupt_id:
        decision = "reject" if is_injection else "approve"
        response_msg = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=interrupt_id,
                        name="adk_request_input",
                        response={"decision": decision}
                    )
                )
            ]
        )
        
        events_turn_1 = []
        events_turn_1.append({
            "author": "user",
            "content": to_dict(response_msg)
        })
        
        runner_events_2 = list(runner.run(new_message=response_msg, user_id="eval_user", session_id=session.id))
        
        for event in runner_events_2:
            if event.content:
                is_tool = any(p.function_response for p in event.content.parts)
                author = "tool" if is_tool else "expense_processor"
                events_turn_1.append({
                    "author": author,
                    "content": to_dict(event.content)
                })
                
        turns.append({
            "turn_index": 1,
            "events": events_turn_1
        })
        
    return {
        "agents": {
            "expense_processor": {
                "agent_id": "expense_processor",
                "instruction": "Ambient expense-approval workflow agent."
            }
        },
        "turns": turns
    }

def main():
    dataset_path = "tests/eval/datasets/basic-dataset.json"
    output_path = "artifacts/traces/generated_traces.json"
    
    print(f"Loading dataset from {dataset_path}...")
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    eval_cases = []
    
    for case in dataset["eval_cases"]:
        case_id = case["eval_case_id"]
        trigger_payload = case["prompt"]["parts"][0]["text"]
        print(f"Running evaluation case: {case_id}...")
        
        agent_data = run_scenario(case_id, trigger_payload)
        
        eval_cases.append({
            "eval_case_id": case_id,
            "agent_data": agent_data
        })
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"eval_cases": eval_cases}, f, indent=2)
        
    print(f"Successfully wrote generated traces to {output_path}!")

if __name__ == "__main__":
    main()
