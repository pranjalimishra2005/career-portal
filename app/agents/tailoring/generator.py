import json
from typing import Optional
from app.core.config import BASE_DIR
from app.db.job_schema import JobPosting
from app.db.profile_schema import UserProfile
from app.db.retriever import query_profile
from app.llm.factory import get_llm_provider
from app.agents.tailoring.schema import TailoredResume, TailoredCoverLetter


def load_candidate_profile() -> Optional[UserProfile]:
    """Helper to load ground-truth candidate profile if not passed explicitly."""
    profile_path = BASE_DIR / "data" / "profile" / "profile.json"
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return UserProfile(**json.load(f))
        except Exception:
            pass
    return None


async def generate_tailored_resume(job: JobPosting, profile: Optional[UserProfile] = None) -> TailoredResume:
    """
    Generates a tailored resume targeting a specific job posting.
    Retrieves candidate's real profile chunks and maps them to job requirements.
    Strictly forbids inventing employment or projects.
    """
    if profile is None:
        profile = load_candidate_profile()

    # 1. Retrieve the candidate's most relevant facts from ChromaDB
    retrieved_facts = query_profile(
        query_text=f"{job.title} {job.description[:400]}",
        top_k=8
    )
    
    facts_context = "\n\n".join([
        f"Fact [ID: {f.chunk_id}] ({f.source_type}):\n{f.content}"
        for f in retrieved_facts
    ])

    has_work_exp = bool(profile and profile.experience and len(profile.experience) > 0)
    real_project_titles = [p.title for p in profile.projects] if (profile and profile.projects) else []

    exp_constraint = (
        "Candidate has verifiable work experience in facts."
        if has_work_exp
        else (
            "CRITICAL: The candidate has NO prior professional work experience (experience: []). "
            "The 'experience' array in your JSON output MUST BE AN EMPTY LIST: []. "
            "DO NOT invent any companies, internships, employers, or roles under any circumstances! "
            "Highlight their technical projects and academic training instead."
        )
    )

    proj_constraint = (
        f"CRITICAL: The candidate's ONLY real projects are: {real_project_titles}. "
        "Use ONLY these projects. DO NOT invent any new project titles or companies."
        if real_project_titles
        else "Use only projects mentioned in CANDIDATE FACTS."
    )

    prompt = f"""
You are an expert executive resume writer. Tailor the candidate's resume for the target job below.

CRITICAL INTEGRITY CONSTRAINTS:
1. NEVER invent, fabricate, or exaggerate experiences, skills, metrics, or technologies.
2. Use ONLY facts directly stated in the CANDIDATE FACTS section.
3. Every bullet point MUST cite the exact Fact ID from which it was derived in source_chunk_ids (e.g. ["proj_0", "skill_0"]).
4. {exp_constraint}
5. {proj_constraint}

TARGET JOB:
Title: {job.title}
Company: {job.company}
Description:
{job.description}

CANDIDATE FACTS (REAL PROFILE):
{facts_context}
"""

    llm = get_llm_provider()
    tailored_resume = await llm.generate_structured(
        prompt=prompt,
        response_model=TailoredResume,
        system_instruction=(
            "You are a strict, factual resume writer. Emphasize matching skills. "
            "Never hallucinate. Always cite exact source chunk IDs. Output valid JSON."
        ),
        temperature=0.1
    )
    
    # Ensure job ID matches
    tailored_resume.target_job_id = job.id
    tailored_resume.target_role = job.title
    tailored_resume.target_company = job.company
    
    return tailored_resume


async def generate_tailored_cover_letter(job: JobPosting, profile: Optional[UserProfile] = None) -> TailoredCoverLetter:
    """
    Generates a targeted, concise cover letter using only verified profile facts.
    """
    if profile is None:
        profile = load_candidate_profile()

    candidate_name = profile.full_name if profile else "Applicant"

    retrieved_facts = query_profile(
        query_text=f"{job.title} {job.company} {job.description[:300]}",
        top_k=6
    )
    
    facts_context = "\n\n".join([
        f"Fact [ID: {f.chunk_id}]: {f.content}"
        for f in retrieved_facts
    ])

    has_work_exp = bool(profile and profile.experience and len(profile.experience) > 0)
    exp_tone = (
        "Discuss relevant work experience from the candidate facts."
        if has_work_exp
        else (
            "The candidate is a student/graduate with no prior corporate employment. "
            "Write honestly and enthusiastically highlighting their university background, hands-on projects, "
            "and technical foundation. DO NOT invent past employers or internships."
        )
    )

    prompt = f"""
Write a professional, targeted 3-paragraph cover letter for candidate {candidate_name} applying to this role.

CRITICAL INTEGRITY CONSTRAINTS:
1. Base all statements of experience and accomplishments ONLY on the provided CANDIDATE FACTS.
2. {exp_tone}
3. Keep the tone professional, confident, and concise.
4. Sign off formally with:
Sincerely,
{candidate_name}
(DO NOT use 'Alex Mercer' or any other name).

TARGET JOB:
Role: {job.title}
Company: {job.company}
Description:
{job.description}

CANDIDATE FACTS:
{facts_context}
"""

    llm = get_llm_provider()
    cover_letter = await llm.generate_structured(
        prompt=prompt,
        response_model=TailoredCoverLetter,
        system_instruction="Write a truthful, compelling cover letter grounded strictly in real facts. Output valid JSON.",
        temperature=0.1
    )
    
    cover_letter.target_job_id = job.id
    cover_letter.company_name = job.company
    cover_letter.role_title = job.title
    cover_letter.sign_off = f"Sincerely,\n{candidate_name}"
    
    return cover_letter