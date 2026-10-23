import json
from typing import Optional
from mcp.server.fastmcp import FastMCP

from app.db.sqlite_client import list_jobs, get_job_by_id
from app.tools.job_fetcher import get_sample_jobs, fetch_greenhouse_jobs

# Initialize FastMCP Server
mcp = FastMCP("job-search-server")


@mcp.tool()
def get_matched_jobs(limit: int = 10, min_score: float = 60.0) -> str:
    """
    Retrieves jobs that have been evaluated and matched to candidate profile.
    
    Args:
        limit: Maximum number of jobs to return (default: 10)
        min_score: Minimum LLM match score cutoff (default: 60.0)
        
    Returns:
        JSON string containing matched jobs with scores and reasoning.
    """
    matched = list_jobs(status="matched", limit=limit)
    
    # Filter by minimum score if evaluated
    results = []
    for job in matched:
        # If evaluated by LLM, LLM score takes precedence; otherwise fall back to embedding
        is_matched = (job.llm_score >= min_score) if job.llm_score is not None else ((job.embedding_score or 0) >= 0.6)
        if is_matched:
            results.append({
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "llm_score": job.llm_score,
                "embedding_score": job.embedding_score,
                "reasoning": job.llm_reasoning,
                "status": job.status
            })
            
    return json.dumps(results, indent=2)


@mcp.tool()
def get_job_details(job_id: str) -> str:
    """
    Fetches the full description and requirements for a specific job ID.
    
    Args:
        job_id: The unique identifier of the job (e.g. 'sample_backend_01')
        
    Returns:
        JSON string with full job details or an error message if not found.
    """
    job = get_job_by_id(job_id)
    if not job:
        return json.dumps({"error": f"Job with ID '{job_id}' not found."})
        
    return json.dumps({
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "platform": job.platform,
        "description": job.description,
        "llm_score": job.llm_score,
        "status": job.status
    }, indent=2)


@mcp.tool()
def seed_or_refresh_sample_jobs() -> str:
    """
    Seeds local SQLite database with fresh benchmark jobs (backend, fullstack, mismatch).
    Useful for testing agents without external API calls.
    """
    jobs = get_sample_jobs()
    return json.dumps({
        "status": "success",
        "message": f"Seeded {len(jobs)} sample jobs into SQLite database.",
        "job_ids": [j.id for j in jobs]
    }, indent=2)


if __name__ == "__main__":
    mcp.run()