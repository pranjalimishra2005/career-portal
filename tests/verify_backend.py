from fastapi.testclient import TestClient
from app.backend.main import app

client = TestClient(app)


def test_backend_routes():
    print("=== Testing FastAPI Core Routes ===")
    
    # 1. Health
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    print(f"1. Health Check: {res_health.json()}")

    # 2. Profile
    res_profile = client.get("/api/profile")
    assert res_profile.status_code == 200
    profile_data = res_profile.json()
    print(f"2. Profile Loaded: {profile_data['full_name']} ({profile_data['email']})")

    # 3. Seed Sample Jobs
    res_seed = client.post("/api/jobs/seed-sample")
    assert res_seed.status_code == 200
    print(f"3. Seed Jobs: {res_seed.json()['message']}")

    # 4. List Jobs
    res_jobs = client.get("/api/jobs")
    assert res_jobs.status_code == 200
    jobs = res_jobs.json()
    print(f"4. Jobs in SQLite: {len(jobs)} jobs found")

    print("\nAll FastAPI backend routes verified successfully!")


if __name__ == "__main__":
    test_backend_routes()