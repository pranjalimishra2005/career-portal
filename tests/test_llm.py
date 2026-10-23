import pytest
from pydantic import BaseModel, Field
from app.llm.factory import get_llm_provider
from app.llm.base import BaseLLMProvider


class SampleEvaluation(BaseModel):
    is_match: bool = Field(..., description="Whether candidate matches requirements")
    score: float = Field(..., description="Match score from 0.0 to 1.0")
    key_reasons: list[str] = Field(..., description="List of reasons")


@pytest.mark.asyncio
async def test_llm_factory_instantiation():
    """Verify factory returns an instance implementing BaseLLMProvider."""
    llm = get_llm_provider()
    assert isinstance(llm, BaseLLMProvider)


@pytest.mark.asyncio
async def test_llm_text_generation():
    """Verify free LLM provider can generate plain text."""
    llm = get_llm_provider()
    response = await llm.generate_text("Reply with the single word: READY")
    assert "READY" in response.upper()


@pytest.mark.asyncio
async def test_llm_structured_output():
    """Verify LLM strictly outputs and validates against a Pydantic model."""
    llm = get_llm_provider()
    prompt = (
        "Candidate has 2 years of Python and FastAPI experience. "
        "Job requires Python and backend development. "
        "Evaluate the match."
    )

    result = await llm.generate_structured(prompt, SampleEvaluation)

    assert isinstance(result, SampleEvaluation)
    assert isinstance(result.is_match, bool)
    assert 0.0 <= result.score <= 1.0
    assert len(result.key_reasons) > 0
    