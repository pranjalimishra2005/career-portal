import pytest
from app.db.job_schema import JobPosting
from app.db.sqlite_client import init_db, save_job, get_job_by_id
from app.tools.job_fetcher import clean_job_description, get_sample_jobs
from app.agents.matching.embedding_ranker import rank_jobs_by_embedding
from app.agents.matching.llm_reranker import evaluate_job_with_llm


@pytest.fixture(autouse=True)
def setup_database():
    """Ensures clean database tables before running matching tests."""
    init_db()


def test_clean_job_description_html_stripping():
    """Verify HTML tags and entities are stripped cleanly regardless of format."""
    dirty_html = "<div><h3>Software Engineer</h3><p>We use Python &amp; FastAPI.</p><br></div>"
    cleaned = clean_job_description(dirty_html)
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert "&amp;" not in cleaned
    assert "Python & FastAPI" in cleaned


def test_stage1_embedding_dynamic_ranking():
    """
    Verify Stage 1 embedding ranker scores jobs proportionally to profile overlap.
    Roles matching candidate skills must score significantly higher than mismatch roles.
    """
    sample_jobs = get_sample_jobs()
    ranked = rank_jobs_by_embedding(sample_jobs, threshold=0.45)

    scores_by_id = {j.id: j.embedding_score for j in ranked}

    # Verify that roles overlapping with the active profile score higher than total mismatches
    assert scores_by_id["sample_backend_01"] > scores_by_id["sample_mismatch_03"]
    assert scores_by_id["sample_fullstack_02"] > scores_by_id["sample_mismatch_03"]


@pytest.mark.asyncio
async def test_stage2_llm_reranker_evaluation():
    """Verify Stage 2 LLM generates valid structured evaluation with evidence."""
    backend_job = get_job_by_id("sample_backend_01")
    assert backend_job is not None

    evaluation = await evaluate_job_with_llm(backend_job)

    # Must produce bounded scores and structured verdict
    assert 0 <= evaluation.match_score <= 100
    assert evaluation.verdict in ["strong_match", "moderate_match", "no_match"]
    assert len(evaluation.explanation) > 10

    # Verify SQLite was updated with the decision
    updated_job = get_job_by_id("sample_backend_01")
    assert updated_job.status in ["matched", "rejected"]
    assert updated_job.llm_score == float(evaluation.match_score)