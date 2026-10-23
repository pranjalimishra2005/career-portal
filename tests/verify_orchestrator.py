import asyncio
from app.core.config import settings
from app.agents.orchestrator import start_application_pipeline, resume_with_human_decision


async def main():
    print("=== Step 1: Starting LangGraph Application Pipeline ===")
    job_id = "sample_backend_01"
    run_result = await start_application_pipeline(job_id)

    thread_id = run_result["thread_id"]
    next_node = run_result["next_node"]
    state = run_result["state"]

    print(f"\nWorkflow paused at: {next_node}")
    print(f"Match Score: {state['match_evaluation'].match_score}/100")
    print(f"Audit Passed: {state['audit_report'].passed_audit}")
    print(f"Direct Form Link: {state.get('application_url')}")
    print(f"Preview Screenshot: {state['preview_screenshot_path']}\n")

    if not settings.HEADLESS_BROWSER:
        print("=" * 65)
        print(">>> LIVE POP-UP ACTIVE: Look at your screen!")
        print(">>> A Chromium window is open right now with all fields filled in.")
        print(">>> You can scroll, inspect, or edit any field in the browser.")
        print("=" * 65)
        input(">>> Press Enter in this terminal to APPROVE & submit... ")

    print("\n=== Step 2: Finalizing Human Approval ===")
    decision_result = await resume_with_human_decision(thread_id=thread_id, approve=True)
    print(f"Resume Result: {decision_result['message']}")


if __name__ == "__main__":
    asyncio.run(main())