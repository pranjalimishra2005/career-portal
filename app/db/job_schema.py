from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    id: str = Field(..., description="Unique job ID (e.g. greenhouse_12345 or slug)")
    title: str = Field(..., description="Job title, e.g. Backend Software Engineer")
    company: str = Field(..., description="Company name")
    location: str = Field(default="Remote")
    url: str = Field(..., description="Direct application page URL")
    description: str = Field(..., description="Raw text of the job description")
    platform: str = Field(default="greenhouse", description="ATS platform: greenhouse, lever, ashby, custom")
    embedding_score: Optional[float] = Field(default=None, description="Stage 1 similarity score (0.0 - 1.0)")
    llm_score: Optional[float] = Field(default=None, description="Stage 2 LLM match score (0 - 100)")
    llm_reasoning: Optional[str] = Field(default=None, description="LLM bulleted explanation of fit")
    status: str = Field(default="discovered", description="discovered | matched | rejected | pending_approval | applied")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())