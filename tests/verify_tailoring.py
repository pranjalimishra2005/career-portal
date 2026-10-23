import asyncio
from app.db.sqlite_client import get_job_by_id
from app.agents.tailoring.generator import generate_tailored_resume
from app.agents.tailoring.verifier import audit_tailored_document, verify_claim


async def main():
    print("--- Test 1: Verifying Generated Real Resume ---")
    job = get_job_by_id("sample_backend_01")
    resume = await generate_tailored_resume(job)
    report = await audit_tailored_document(resume)
    print(f"Document: {report.document_type} | Passed Audit: {report.passed_audit}")
    print(f"Claims: {report.verified_claims}/{report.total_claims} verified.")
    print(f"Summary: {report.audit_summary}\n")

    if not report.passed_audit:
        print("Auditor Flagged the following unsupported claims:")
        for c in report.claims:
            if not c.is_supported:
                print(f" - REJECTED: '{c.claim_text}'")
                print(f"   REASON: {c.reason}\n")

    print("--- Test 2: Testing Fraud Detector on Fabricated Claim ---")
    fake_claim = "Led a team of 15 engineers to migrate AWS infrastructure to Kubernetes."
    fake_check = await verify_claim(fake_claim)
    print(f"Claim: '{fake_claim}'")
    print(f"Is Supported: {fake_check.is_supported}")
    print(f"Auditor Reason: {fake_check.reason}")


if __name__ == "__main__":
    asyncio.run(main())