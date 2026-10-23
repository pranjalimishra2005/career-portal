from app.agents.orchestrator_state import AgentState
from app.agents.orchestrator_nodes import load_profile_node


def main():
    state = AgentState(job_id="sample_backend_01")
    res = load_profile_node(state)
    profile = res["profile"]
    job = res["job"]
    print("Orchestrator Nodes Verified!")
    print(f" - Candidate: {profile.full_name} ({profile.email})")
    print(f" - Target Job: {job.title} at {job.company}")
    print(f" - Next Step: {res['current_step']}")


if __name__ == "__main__":
    main()