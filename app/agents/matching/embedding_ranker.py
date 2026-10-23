from typing import List, Tuple
from app.db.job_schema import JobPosting
from app.db.retriever import query_profile
from app.db.sqlite_client import save_job


def compute_job_embedding_score(job: JobPosting, top_k: int = 3) -> float:
    """
    Computes a mathematical similarity score between a job description and the profile.
    
    How it works:
    1. Extracts the core job title + description snippet.
    2. Queries ChromaDB for the top_k most relevant chunks in your profile.
    3. Calculates the weighted average similarity score across the top matches.
    """
    # Create search query focused on the role and its technical requirements
    query_text = f"Role: {job.title}\nRequirements: {job.description[:400]}"
    
    matches = query_profile(query_text=query_text, top_k=top_k)
    
    if not matches:
        return 0.0

    # Average the top retrieved scores (each score is between 0.0 and 1.0)
    total_score = sum(match.similarity_score for match in matches)
    avg_score = total_score / len(matches)
    
    return round(avg_score, 4)


def rank_jobs_by_embedding(
    jobs: List[JobPosting],
    threshold: float = 0.45
) -> List[JobPosting]:
    """
    Ranks a list of jobs by embedding similarity.
    Updates the score in SQLite, and filters out jobs below the minimum threshold.
    Returns the surviving jobs sorted from highest to lowest score.
    """
    scored_jobs: List[JobPosting] = []

    for job in jobs:
        score = compute_job_embedding_score(job)
        job.embedding_score = score
        
        # Calibrated 0-100 score: cosine [0.50, 0.75] -> [0, 100]
        calibrated_score = round(((score - 0.50) / 0.25) * 100) if score else 0
        
        # Only tag as 'matched' if score strictly > 60
        if calibrated_score > 60 and job.status not in ["applied", "interview", "offer", "rejected_by_user"]:
            job.status = "matched"
            scored_jobs.append(job)
        elif job.status not in ["applied", "interview", "offer", "rejected_by_user"]:
            job.status = "discovered"
            scored_jobs.append(job)
            
        save_job(job)

    # Sort surviving jobs in descending order (highest match first)
    scored_jobs.sort(key=lambda j: j.embedding_score or 0.0, reverse=True)
    return scored_jobs