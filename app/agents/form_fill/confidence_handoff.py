from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.db.retriever import query_profile
from app.llm.factory import get_llm_provider
from app.tools.field_detector import DetectedField


class FieldAnswerResolution(BaseModel):
    field_id: str
    label: str
    value: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    source_chunk_ids: List[str] = Field(default_factory=list)
    requires_human_input: bool = Field(
        default=False,
        description="True if retrieval confidence is low or fact is missing from profile"
    )
    explanation: str


class ScreeningAnswerDecision(BaseModel):
    can_answer: bool = Field(
        ...,
        description="True ONLY if the candidate facts genuinely contain the information needed to answer the question"
    )
    answer: Optional[str] = Field(
        default=None,
        description="Concise, professional 1-2 sentence answer if can_answer is True"
    )
    reason: str = Field(
        ...,
        description="Why the facts do or do not answer the question"
    )


CONFIDENCE_THRESHOLD = 0.55


async def resolve_field_with_confidence(field: DetectedField) -> FieldAnswerResolution:
    """
    Evaluates whether an open-ended screening question can be answered
    with high confidence from candidate profile facts.
    
    If confidence < 0.55 or facts are missing, flags requires_human_input = True.
    """
    # 1. Query ChromaDB for top 3 facts matching the field label
    matches = query_profile(query_text=field.label_text, top_k=3)

    if not matches or matches[0].similarity_score < CONFIDENCE_THRESHOLD:
        score = matches[0].similarity_score if matches else 0.0
        return FieldAnswerResolution(
            field_id=field.field_id,
            label=field.label_text,
            value=None,
            confidence_score=round(score, 4),
            source_chunk_ids=[],
            requires_human_input=True,
            explanation=(
                f"Low retrieval confidence ({score:.2f} < {CONFIDENCE_THRESHOLD}). "
                f"Candidate profile has no verified facts for: '{field.label_text}'."
            )
        )

    top_score = matches[0].similarity_score
    chunk_ids = [m.chunk_id for m in matches]
    facts_context = "\n\n".join([f"[{m.chunk_id}]: {m.content}" for m in matches])

    # 2. Structured decision using Pydantic
    prompt = f"""
APPLICATION QUESTION:
"{field.label_text}"

VERIFIED CANDIDATE FACTS:
{facts_context}

EVALUATION RULES:
1. If the candidate facts genuinely provide the answer, set can_answer = true and write a concise 1-2 sentence answer.
2. If the facts are merely topically related (e.g. mentions security in code, but question asks for Military Security Clearance), set can_answer = false.
3. NEVER fabricate dates, clearances, or experiences not explicitly in the facts.
"""
    llm = get_llm_provider()
    decision = await llm.generate_structured(
        prompt=prompt,
        response_model=ScreeningAnswerDecision,
        system_instruction="Strict factual decision maker. Set can_answer=false if fact is missing. Output valid JSON.",
        temperature=0.0
    )

    if not decision.can_answer or not decision.answer:
        return FieldAnswerResolution(
            field_id=field.field_id,
            label=field.label_text,
            value=None,
            confidence_score=round(top_score, 4),
            source_chunk_ids=chunk_ids,
            requires_human_input=True,
            explanation=f"Facts matched topically but did not contain the specific answer: {decision.reason}"
        )

    return FieldAnswerResolution(
        field_id=field.field_id,
        label=field.label_text,
        value=decision.answer.strip(),
        confidence_score=round(top_score, 4),
        source_chunk_ids=chunk_ids,
        requires_human_input=False,
        explanation=decision.reason
    )