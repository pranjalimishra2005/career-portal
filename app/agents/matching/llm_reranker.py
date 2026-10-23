from typing import List, Optional
from pydantic import BaseModel, Field

from app.db.job_schema import JobPosting
from app.db.sqlite_client import save_job
from app.db.retriever import query_profile
from app.llm.factory import get_llm_provider


class JobMatchEvaluation(BaseModel):
    match_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Fit score from 0 (total mismatch) to 100 (perfect fit)"
    )
    verdict: str = Field(
        ...,
        description="'strong_match' (80-100), 'moderate_match' (60-79), or 'no_match' (0-59)"
    )
    matched_skills: List[str] = Field(
        default_factory=list,
        description="Skills candidate possesses that the job asks for"
    )
    missing_requirements: List[str] = Field(
        default_factory=list,
        description="Required qualifications the candidate lacks"
    )
    explanation: str = Field(
        ...,
        description="2-3 sentence factual explanation of the verdict"
    )


async def evaluate_job_with_llm(job: JobPosting) -> JobMatchEvaluation:
    """
    Evaluates a single job posting against candidate profile facts using the LLM.
    """
    # 1. Retrieve the most relevant facts from candidate profile for this job
    retrieved_facts = query_profile(
        query_text=f"{job.title} {job.description[:300]}",
        top_k=4
    )
    facts_text = "\n\n".join([f"- [{f.source_type}]: {f.content}" for f in retrieved_facts])

    # 2. Construct the prompt
    prompt = f"""
You are an expert technical recruiter evaluating whether a candidate is qualified for a job.

CANDIDATE FACTS (from real profile):
{facts_text}

JOB POSTING:
Title: {job.title}
Company: {job.company}
Description:
{job.description}

EVALUATION RULES:
1. Base your evaluation strictly on the candidate's real profile facts provided above. Do NOT assume skills not mentioned.
2. If the candidate lacks core hard requirements (e.g. 5+ years of Swift/iOS for an iOS role, but candidate is Python backend), assign verdict 'no_match' with score below 40.
3. Be fair to junior/internship roles if core language matches (e.g. Python, FastAPI, Docker).
"""

    llm = get_llm_provider()
    evaluation = await llm.generate_structured(
        prompt=prompt,
        response_model=JobMatchEvaluation,
        system_instruction="You are a strict, objective technical recruiter. Output only valid JSON.",
        temperature=0.1
    )

    # 3. Update job record and persist to SQLite
    job.llm_score = float(evaluation.match_score)
    job.llm_reasoning = (
        f"Verdict: {evaluation.verdict.upper()} ({evaluation.match_score}/100)\n"
        f"Matched Skills: {', '.join(evaluation.matched_skills) if evaluation.matched_skills else 'None'}\n"
        f"Missing: {', '.join(evaluation.missing_requirements) if evaluation.missing_requirements else 'None'}\n"
        f"Reason: {evaluation.explanation}"
    )

    if evaluation.match_score >= 60:
        job.status = "matched"
    else:
        job.status = "rejected"

    save_job(job)
    return evaluation