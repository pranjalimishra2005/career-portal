from typing import List, Dict, Any
from pydantic import BaseModel, Field
from app.db.profile_schema import UserProfile


class ProfileChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique ID for this chunk")
    content: str = Field(..., description="Text content to be embedded and searched")
    source_type: str = Field(..., description="Section type: summary, education, experience, project, skill, faq")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structured attributes for filtered retrieval")


def chunk_profile(profile: UserProfile) -> List[ProfileChunk]:
    """
    Decomposes a UserProfile into focused, semantic chunks.
    Each chunk is self-contained so the embedding vector accurately captures its meaning.
    """
    chunks: List[ProfileChunk] = []

    # 1. Summary Chunk
    if profile.summary:
        chunks.append(
            ProfileChunk(
                chunk_id="summary_0",
                content=f"Professional Summary for {profile.full_name}:\n{profile.summary}",
                source_type="summary",
                metadata={"title": "Professional Summary", "author": profile.full_name}
            )
        )

    # 2. Education Chunks
    for i, edu in enumerate(profile.education):
        end_str = str(edu.end_year) if edu.end_year else "Present"
        content = (
            f"Education: {edu.degree} in {edu.field_of_study}\n"
            f"Institution: {edu.institution} ({edu.start_year} - {end_str})\n"
        )
        if edu.gpa:
            content += f"GPA: {edu.gpa}"

        chunks.append(
            ProfileChunk(
                chunk_id=f"edu_{i}",
                content=content.strip(),
                source_type="education",
                metadata={"institution": edu.institution, "degree": edu.degree}
            )
        )

    # 3. Work Experience Chunks (one chunk per job role)
    for i, exp in enumerate(profile.experience):
        highlights_text = "\n".join([f"- {hl}" for hl in exp.highlights])
        tech_text = ", ".join(exp.technologies) if exp.technologies else "None listed"

        content = (
            f"Work Experience: {exp.role} at {exp.company}\n"
            f"Location: {exp.location} | Period: {exp.start_date} - {exp.end_date}\n"
            f"Technologies Used: {tech_text}\n"
            f"Key Contributions:\n{highlights_text}"
        )

        chunks.append(
            ProfileChunk(
                chunk_id=f"exp_{i}",
                content=content.strip(),
                source_type="experience",
                metadata={"company": exp.company, "role": exp.role, "tech": tech_text}
            )
        )

    # 4. Project Chunks (one chunk per project)
    for i, proj in enumerate(profile.projects):
        highlights_text = "\n".join([f"- {hl}" for hl in proj.highlights])
        tech_text = ", ".join(proj.technologies) if proj.technologies else "None listed"

        content = (
            f"Project: {proj.title}\n"
            f"Description: {proj.description}\n"
            f"Technologies: {tech_text}\n"
        )
        if proj.repo_url:
            content += f"Repository: {proj.repo_url}\n"
        if proj.live_url:
            content += f"Live URL: {proj.live_url}\n"
        if highlights_text:
            content += f"Highlights:\n{highlights_text}"

        chunks.append(
            ProfileChunk(
                chunk_id=f"proj_{i}",
                content=content.strip(),
                source_type="project",
                metadata={"title": proj.title, "tech": tech_text}
            )
        )

    # 5. Skills Chunks (one chunk per category)
    for i, skill_cat in enumerate(profile.skills):
        skills_str = ", ".join(skill_cat.skills)
        content = f"Technical Skills ({skill_cat.category}): {skills_str}"

        chunks.append(
            ProfileChunk(
                chunk_id=f"skill_{i}",
                content=content,
                source_type="skill",
                metadata={"category": skill_cat.category}
            )
        )

    # 6. FAQ Chunks (one chunk per Q&A)
    for i, faq in enumerate(profile.faqs):
        tags_str = ", ".join(faq.tags) if faq.tags else ""
        content = (
            f"Frequently Asked Application Question:\n"
            f"Question: {faq.question}\n"
            f"Answer: {faq.answer}"
        )

        chunks.append(
            ProfileChunk(
                chunk_id=f"faq_{i}",
                content=content,
                source_type="faq",
                metadata={"question": faq.question, "tags": tags_str}
            )
        )

    # 7. Screening & Work Authorization Vault Chunks
    if getattr(profile, "screening", None):
        s = profile.screening
        auth_str = "Yes, legally authorized to work" if s.authorized_to_work else "No, not legally authorized"
        sponsor_str = "Yes, requires visa sponsorship" if s.requires_sponsorship else "No, does not require visa sponsorship"
        reloc_str = "Yes, open to relocation" if s.willing_to_relocate else "No, not open to relocation"

        screening_content = (
            f"Candidate Work Authorization and Screening Preferences for {profile.full_name}:\n"
            f"- Legal Work Authorization: {auth_str}\n"
            f"- Visa Sponsorship Need: {sponsor_str}\n"
            f"- Notice Period / Earliest Availability: {s.notice_period}\n"
            f"- Relocation Preference: {reloc_str}\n"
            f"- Work Mode Preference: {s.work_location_preference}\n"
            f"- Preferred Pronouns: {s.pronouns or 'Not specified'}\n"
            f"- Expected Compensation: {s.expected_salary or 'Negotiable'}"
        )
        chunks.append(
            ProfileChunk(
                chunk_id="screening_0",
                content=screening_content,
                source_type="screening",
                metadata={"title": "Screening & Work Authorization Vault", "author": profile.full_name}
            )
        )

        for i, qa in enumerate(s.custom_qa):
            chunks.append(
                ProfileChunk(
                    chunk_id=f"screening_qa_{i}",
                    content=f"Candidate Screening Answer:\nQuestion: {qa.question}\nAnswer: {qa.answer}",
                    source_type="screening",
                    metadata={"question": qa.question}
                )
            )

    return chunks