import asyncio
from app.tools.field_detector import DetectedField
from app.agents.form_fill.confidence_handoff import resolve_field_with_confidence


async def main():
    print("--- Test 1: High Confidence Screening Question ---")
    field1 = DetectedField(
        field_id="q1",
        selector="#q1",
        tag_name="textarea",
        label_text="Describe your experience with async Python microservices and caching",
        semantic_type="open_ended_question"
    )
    res1 = await resolve_field_with_confidence(field1)
    print(f"Confidence: {res1.confidence_score} | Needs Human: {res1.requires_human_input}")
    print(f"Generated Value: {res1.value}\n")

    print("--- Test 2: Unanswerable / Missing Fact Question ---")
    field2 = DetectedField(
        field_id="q2",
        selector="#q2",
        tag_name="input",
        label_text="What is your active military security clearance level and issuing agency?",
        semantic_type="open_ended_question"
    )
    res2 = await resolve_field_with_confidence(field2)
    print(f"Confidence: {res2.confidence_score} | Needs Human: {res2.requires_human_input}")
    print(f"Reason: {res2.explanation}")


if __name__ == "__main__":
    asyncio.run(main())