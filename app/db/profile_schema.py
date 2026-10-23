from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Education(BaseModel):
    institution: str = Field(..., description="College or University name")
    degree: str = Field(..., description="Degree type (e.g., B.Tech, B.S., High School)")
    field_of_study: Optional[str] = Field(default="", description="Major or Stream (e.g., Computer Science, Science)")
    start_year: Optional[int] = Field(default=None, description="Starting year (optional)")
    end_year: Optional[int] = Field(default=None, description="Graduation year or expected completion")
    gpa: Optional[str] = Field(default=None, description="GPA or percentage")


class WorkExperience(BaseModel):
    company: str
    role: str
    location: Optional[str] = Field(default="", description="City, State or Remote")
    start_date: Optional[str] = Field(default="", description="e.g., 'June 2023'")
    end_date: Optional[str] = Field(default="", description="e.g., 'August 2023' or 'Present'")
    highlights: List[str] = Field(
        default_factory=list,
        description="Key achievements and technical bullet points"
    )
    technologies: List[str] = Field(
        default_factory=list,
        description="Tools, languages, and frameworks used"
    )


class Project(BaseModel):
    title: str
    description: Optional[str] = Field(default="", description="Project overview")
    technologies: List[str] = Field(
        default_factory=list,
        description="Tools, languages, and libraries used"
    )
    repo_url: Optional[str] = None
    live_url: Optional[str] = None
    highlights: List[str] = Field(
        default_factory=list,
        description="Quantifiable metrics or key technical accomplishments"
    )


class SkillCategory(BaseModel):
    category: str = Field(..., description="e.g. Languages, Frameworks, Cloud, Databases")
    skills: List[str] = Field(default_factory=list)


class FAQItem(BaseModel):
    question: str = Field(..., description="Common application question")
    answer: str = Field(..., description="Your factual personal response")
    tags: List[str] = Field(default_factory=list)


class ScreeningPreferences(BaseModel):
    authorized_to_work: Optional[bool] = Field(
        default=True,
        description="Are you legally authorized to work in the target country?"
    )
    requires_sponsorship: Optional[bool] = Field(
        default=False,
        description="Do you or will you in the future require visa sponsorship?"
    )
    notice_period: Optional[str] = Field(
        default="Immediate",
        description="e.g. Immediate, 2 weeks, 1 month, 3 months"
    )
    willing_to_relocate: Optional[bool] = Field(
        default=True,
        description="Are you open to relocating for this role?"
    )
    work_location_preference: Optional[str] = Field(
        default="Flexible",
        description="Remote | Hybrid | On-site | Flexible"
    )
    pronouns: Optional[str] = Field(
        default="",
        description="Preferred pronouns (e.g. She/Her, He/Him, They/Them, Any/All)"
    )
    expected_salary: Optional[str] = Field(
        default="Negotiable",
        description="Expected compensation or 'Negotiable'"
    )
    custom_qa: List[FAQItem] = Field(
        default_factory=list,
        description="User-defined Q&A for specific custom ATS screening questions"
    )


class UserProfile(BaseModel):
    full_name: str
    email: str = Field(..., description="Candidate contact email")
    phone: Optional[str] = Field(default="", description="Candidate phone number")
    location: Optional[str] = Field(default="", description="City, State / Country")
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: Optional[str] = Field(default="", description="Professional summary")
    education: List[Education] = Field(default_factory=list)
    experience: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[SkillCategory] = Field(default_factory=list)
    screening: ScreeningPreferences = Field(
        default_factory=ScreeningPreferences,
        description="Screening & Work Auth Vault for safe ATS question autofill"
    )
    faqs: List[FAQItem] = Field(
        default_factory=list,
        description="Answers to standard ATS questions like work auth, relocation, etc."
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v
