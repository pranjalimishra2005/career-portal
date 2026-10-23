import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from app.db.profile_schema import UserProfile, Education, WorkExperience, Project, SkillCategory, FAQItem
from app.db.chunker import chunk_profile
from app.db.vector_store import index_profile_chunks, get_profile_collection
from app.db.retriever import query_profile


@pytest.fixture
def sample_profile_data():
    profile_path = Path("data/profile/profile.json")
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "full_name": "Alex Mercer",
        "email": "alex.mercer@example.com",
        "phone": "+1 555-0199",
        "location": "San Francisco, CA",
        "summary": "Senior Backend Engineer with 5+ years of experience in Python, FastAPI, and distributed systems.",
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [
            {"category": "Technical", "skills": ["Python", "FastAPI", "Redis"]}
        ]
    }


@pytest.fixture
def populated_profile():
    return UserProfile(
        full_name="Alex Mercer",
        email="alex.mercer@example.com",
        phone="+1 555-0199",
        location="San Francisco, CA",
        summary="Senior Backend Engineer with 5+ years of experience in Python, FastAPI, and distributed systems.",
        education=[
            Education(
                institution="UC Berkeley",
                degree="B.S. Computer Science",
                field_of_study="Computer Science",
                start_year=2015,
                end_year=2019
            )
        ],
        experience=[
            WorkExperience(
                company="TechCorp",
                role="Backend Engineer",
                highlights=["Designed FastAPI microservices handling 10k RPS."],
                technologies=["Python", "FastAPI", "Redis"]
            )
        ],
        projects=[
            Project(
                title="Distributed Task Queue",
                description="Built high-throughput queue using Redis and Python.",
                technologies=["Python", "Redis"],
                highlights=["Reduced latency by 40%"]
            )
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Python", "SQL", "Go"])
        ],
        faqs=[
            FAQItem(
                question="Are you legally authorized to work in the United States?",
                answer="Yes, I am a US citizen and do not require visa sponsorship.",
                tags=["work_auth", "citizenship"]
            )
        ]
    )


def test_profile_schema_validation(sample_profile_data):
    """Verify that valid profile data instantiates successfully."""
    profile = UserProfile(**sample_profile_data)
    assert profile.full_name == sample_profile_data["full_name"]
    assert profile.email == sample_profile_data["email"]


def test_profile_schema_invalid_email():
    """Verify that invalid email raises Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        UserProfile(
            full_name="Invalid User",
            email="not-an-email",  # Invalid
            phone="1234567890",
            location="Anytown",
            summary="Test summary"
        )


def test_chunking_creates_all_expected_types(populated_profile):
    """Verify chunker produces chunks for all sections."""
    chunks = chunk_profile(populated_profile)
    source_types = {chunk.source_type for chunk in chunks}

    expected_types = {"summary", "education", "experience", "project", "skill", "faq"}
    assert expected_types.issubset(source_types)

    # Verify each chunk has non-empty content and an ID
    for c in chunks:
        assert len(c.chunk_id) > 0
        assert len(c.content.strip()) > 0


def test_indexing_and_semantic_retrieval(populated_profile):
    """Verify chunks can be indexed and retrieved semantically."""
    chunks = chunk_profile(populated_profile)
    count = index_profile_chunks(chunks)
    assert count >= len(chunks)

    # Semantic search query for FastAPI / caching
    results = query_profile("experience with FastAPI and caching", top_k=2)
    assert len(results) > 0

    top_result = results[0]
    assert top_result.source_type in ["experience", "project", "skill"]
    assert top_result.similarity_score > 0.4


def test_retrieval_with_source_filter(populated_profile):
    """Verify filtering by source_type (e.g., only FAQs)."""
    chunks = chunk_profile(populated_profile)
    index_profile_chunks(chunks)

    faq_results = query_profile(
        query_text="work authorization visa sponsorship",
        top_k=2,
        source_type="faq"
    )

    assert len(faq_results) > 0
    for res in faq_results:
        assert res.source_type == "faq"
