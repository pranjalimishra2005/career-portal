import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import io
import json
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document

from app.core.config import settings, BASE_DIR
from app.db.profile_schema import UserProfile, ScreeningPreferences
from app.db.job_schema import JobPosting
from app.db.sqlite_client import (
    get_db_connection,
    init_db,
    save_job,
    get_job_by_id,
    list_jobs
)
from app.db.chunker import chunk_profile
from app.db.vector_store import index_profile_chunks
from app.llm.factory import get_llm_provider
from app.tools.job_fetcher import (
    fetch_greenhouse_jobs,
    fetch_jobs_from_any_board,
    get_sample_jobs
)
from app.agents.matching.embedding_ranker import rank_jobs_by_embedding, compute_job_embedding_score
from app.agents.matching.llm_reranker import evaluate_job_with_llm
from app.agents.orchestrator import start_application_pipeline, resume_with_human_decision
from app.agents.orchestrator_nodes import ACTIVE_BROWSERS
from app.agents.tailoring.generator import generate_tailored_resume, generate_tailored_cover_letter
from app.tools.document_exporter import (
    EXPORTS_DIR,
    export_resume_docx,
    export_cover_letter_docx,
    export_resume_pdf,
    export_cover_letter_pdf
)
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL, ensure_default_desktop

EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Autonomous Job Application Agent API",
    description="Backend powering zero-fabrication multi-ATS job application automation.",
    version="1.0.0"
)

# Serve generated exports (screenshots, tailored docx resumes/letters)
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup DB initialization
@app.on_event("startup")
def on_startup():
    init_db()
    ensure_default_desktop()


# Models for requests
class ManualJobRequest(BaseModel):
    title: str
    company: str
    location: Optional[str] = "Remote"
    url: Optional[str] = ""
    description: str


class StartApplicationRequest(BaseModel):
    job_id: str


class DecisionRequest(BaseModel):
    thread_id: str
    approve: bool
    feedback: Optional[str] = ""


class OpenBrowserRequest(BaseModel):
    job_id: str


# Filter out mock jobs universally
MOCK_COMPANIES = {"nexus systems", "horizon apps", "acme ai", "mobileswift labs", "example corp"}

def is_real_job(job: JobPosting) -> bool:
    if not job or not job.id:
        return False
    jid = str(job.id).lower()
    if jid.startswith("sample_") or jid.startswith("test_") or jid.startswith("mock_") or jid == "gh_test_01":
        return False
    company = (job.company or "").strip().lower()
    if company in MOCK_COMPANIES:
        return False
    return True


# --- API ENDPOINTS ---

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Job Application Agent API",
        "groq_configured": bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != "dummy_key_for_now")
    }


@app.get("/test-form")
def serve_test_form():
    """Serves the offline mock ATS form over HTTP for safe inspection."""
    form_path = BASE_DIR / "data" / "test_form.html"
    return FileResponse(form_path)


@app.get("/exports/{filename}")
async def get_export_file(filename: str):
    """Serves generated export files (PDFs, docx resumes/letters, screenshots), generating on-demand if needed."""
    file_path = EXPORTS_DIR / filename

    # On-demand headless PDF rendering if not yet generated
    if not file_path.exists() and filename.endswith(".pdf"):
        try:
            if "_resume.pdf" in filename:
                job_id = filename.replace("_resume.pdf", "")
                job = get_job_by_id(job_id)
                if job:
                    resume = await generate_tailored_resume(job)
                    await export_resume_pdf(resume)
            elif "_cover_letter.pdf" in filename:
                job_id = filename.replace("_cover_letter.pdf", "")
                job = get_job_by_id(job_id)
                if job:
                    letter = await generate_tailored_cover_letter(job)
                    await export_cover_letter_pdf(letter)
        except Exception as e:
            print(f"[ExportAPI] Error during on-demand PDF generation: {e}")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found.")

    if filename.endswith(".png"):
        media_type = "image/png"
    elif filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "application/octet-stream"

    return FileResponse(file_path, media_type=media_type)


@app.post("/api/exports/pdf/{job_id}")
async def generate_pdfs_for_job(job_id: str):
    """Explicitly triggers headless Chromium PDF generation for a role's tailored resume and cover letter."""
    job = get_job_by_id(job_id)
    if not job or not is_real_job(job):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    resume = await generate_tailored_resume(job)
    letter = await generate_tailored_cover_letter(job)

    r_pdf = await export_resume_pdf(resume)
    l_pdf = await export_cover_letter_pdf(letter)

    return {
        "status": "success",
        "job_id": job_id,
        "resume_pdf_url": f"/exports/{r_pdf.name}",
        "cover_letter_pdf_url": f"/exports/{l_pdf.name}"
    }


@app.get("/api/profile")
def get_profile() -> Dict[str, Any]:
    """Returns candidate ground-truth profile from data/profile/profile.json."""
    profile_path = BASE_DIR / "data" / "profile" / "profile.json"
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="Candidate profile not found.")
    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    profile = UserProfile(**data)
    return profile.model_dump()


@app.get("/api/profile/screening")
def get_screening_preferences() -> Dict[str, Any]:
    """Returns candidate screening vault preferences."""
    profile_path = BASE_DIR / "data" / "profile" / "profile.json"
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="Candidate profile not found.")
    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    profile = UserProfile(**data)
    return profile.screening.model_dump()


@app.post("/api/profile/screening")
async def update_screening_preferences(payload: ScreeningPreferences):
    """
    Updates candidate screening preferences (work auth, sponsorship, notice period, relocation, custom Q&A),
    persists to data/profile/profile.json, and re-indexes ChromaDB vector chunks.
    """
    profile_path = BASE_DIR / "data" / "profile" / "profile.json"
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="Candidate profile not found.")
    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    profile = UserProfile(**data)
    profile.screening = payload

    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(profile.model_dump_json(indent=2))

    # Re-index chunks in ChromaDB
    chunks = chunk_profile(profile)
    index_profile_chunks(chunks)

    return {
        "status": "success",
        "message": "Screening preferences vault updated! Answers will safely autofill in ATS applications.",
        "screening": payload.model_dump()
    }


@app.post("/api/profile/upload")
async def upload_resume(file: UploadFile = File(...)):
    """
    Uploads a resume (.pdf, .docx, .txt, or .json), extracts structured UserProfile,
    saves to profile.json, wipes ChromaDB, and completely wipes all jobs and exports
    so that every single piece of data resets fresh for the new candidate.
    """
    filename = file.filename.lower()
    content = await file.read()
    raw_text = ""

    if filename.endswith(".json"):
        try:
            profile_dict = json.loads(content.decode("utf-8"))
            profile = UserProfile(**profile_dict)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid profile JSON: {e}")
    else:
        try:
            if filename.endswith(".pdf"):
                reader = PdfReader(io.BytesIO(content))
                raw_text = "\n".join([page.extract_text() or "" for page in reader.pages])
            elif filename.endswith(".docx"):
                doc = Document(io.BytesIO(content))
                raw_text = "\n".join([p.text for p in doc.paragraphs if p.text])
            else:
                raw_text = content.decode("utf-8", errors="ignore")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract readable text from uploaded file.")

        prompt = (
            f"You are an expert resume parser. Parse this resume text into a strict UserProfile JSON object.\n"
            f"Extract real candidate full name, email, phone, location, summary, education, work experience, projects, and skills.\n"
            f"If the candidate has no prior work experience, set experience to []. Do NOT invent companies or roles.\n\n"
            f"RESUME TEXT:\n{raw_text[:4000]}"
        )
        try:
            llm = get_llm_provider()
            profile = await llm.generate_structured(prompt, UserProfile)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Resume parsing error: {e}")

    # 1. Save strictly to data/profile/profile.json
    profile_path = BASE_DIR / "data" / "profile" / "profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(profile.model_dump_json(indent=2))

    # 2. Chunk profile & re-index into ChromaDB vector store
    chunks = chunk_profile(profile)
    indexed_count = index_profile_chunks(chunks)

    # 3. Complete Lifecycle Reset: Purge ALL previous jobs and application states
    with get_db_connection() as conn:
        conn.execute("DELETE FROM jobs")
        conn.commit()

    # 4. Clean all old generated exports (resumes, cover letters, screenshots)
    if EXPORTS_DIR.exists():
        for item in EXPORTS_DIR.glob("*"):
            if item.is_file():
                try:
                    item.unlink()
                except Exception:
                    pass

    # 5. Close any live browser popups and reset LangGraph state checkpointers
    from app.agents.orchestrator_nodes import ACTIVE_BROWSERS
    for jid, bm in list(ACTIVE_BROWSERS.items()):
        try:
            await bm.close()
        except Exception:
            pass
    ACTIVE_BROWSERS.clear()

    import app.agents.orchestrator as orch_mod
    orch_mod.application_orchestrator = orch_mod.build_application_graph()

    return {
        "status": "success",
        "message": f"Resume uploaded for {profile.full_name}. Everything has been reset: 0 jobs, 0 matches, 0 applications. All previous applied statuses cleared.",
        "profile": profile.model_dump()
    }


@app.get("/api/jobs")
def get_jobs(status: Optional[str] = Query(default=None)) -> List[Dict[str, Any]]:
    """Returns all verified real jobs stored in SQLite across Greenhouse, Ashby, and Lever."""
    jobs = list_jobs(status=status)
    valid_jobs = [j for j in jobs if is_real_job(j)]
    return [job.model_dump() for job in valid_jobs]


@app.delete("/api/jobs")
def clear_all_jobs():
    """Removes all jobs from SQLite database."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM jobs")
        conn.commit()
    return {"status": "success", "message": "All jobs have been removed."}


@app.post("/api/applications/reset")
def reset_all_applications():
    """Resets all jobs in SQLite to 'discovered' status, clearing any applied or rejected flags."""
    with get_db_connection() as conn:
        conn.execute("UPDATE jobs SET status = 'discovered'")
        conn.commit()
    if EXPORTS_DIR.exists():
        for item in EXPORTS_DIR.glob("*"):
            if item.is_file():
                try:
                    item.unlink()
                except Exception:
                    pass
    return {"status": "success", "message": "All job application statuses have been reset to discovered."}


@app.post("/api/jobs/isolate")
def isolate_company(company: str = Query(...)):
    """Removes all jobs except those matching the specified company."""
    comp_clean = company.strip().lower()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM jobs WHERE LOWER(company) != ?", (comp_clean,))
        conn.commit()
    remaining = [j for j in list_jobs() if is_real_job(j)]
    return {
        "status": "success",
        "message": f"Kept only jobs for {company}; removed all other jobs.",
        "jobs": [j.model_dump() for j in remaining]
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    """Retrieves a single job by its ID."""
    job = get_job_by_id(job_id)
    if not job or not is_real_job(job):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job.model_dump()


@app.post("/api/jobs/manual")
def add_manual_job(payload: ManualJobRequest):
    """Adds a custom or manually entered job into the pipeline."""
    job_id = f"custom_{uuid.uuid4().hex[:6]}"
    url = payload.url.strip() if payload.url else "/test-form"
    new_job = JobPosting(
        id=job_id,
        title=payload.title.strip(),
        company=payload.company.strip(),
        location=payload.location.strip() or "Remote",
        url=url,
        description=payload.description.strip(),
        platform="custom",
        status="discovered"
    )
    new_job.embedding_score = compute_job_embedding_score(new_job)
    save_job(new_job)
    return {
        "status": "success",
        "message": f"Added '{new_job.title}' at {new_job.company} to pipeline!",
        "job": new_job.model_dump()
    }


@app.patch("/api/jobs/{job_id}/status")
def update_job_status(job_id: str, status: str = Query(...)):
    """Updates application tracking status: Draft, Discovered, Matched, Applied, Interview, Offer, Rejected."""
    job = get_job_by_id(job_id)
    if not job or not is_real_job(job):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    job.status = status
    save_job(job)
    return {
        "status": "success",
        "message": f"Updated {job.title} status to {status}.",
        "job": job.model_dump()
    }


@app.post("/api/jobs/search-greenhouse")
@app.post("/api/jobs/search")
async def search_greenhouse(
    board: str = Query(default="cloudflare"),
    isolate_company: bool = Query(default=True)
):
    """
    Intelligently searches for real jobs across Greenhouse, Ashby, and Lever:
    1. If isolate_company is True, removes all other jobs so only this company's jobs remain.
    2. Auto-detects ATS platform and fetches live postings.
    3. Pre-ranks all results against candidate profile in ChromaDB.
    """
    query_str = board.strip().lower()
    discovered_jobs: List[JobPosting] = []

    if " " not in query_str:
        discovered_jobs = await fetch_jobs_from_any_board(query_token=query_str, limit=12)

    if discovered_jobs:
        valid_discovered = [j for j in discovered_jobs if is_real_job(j)]
        
        # When clicking or searching a specific company, isolate by removing other jobs
        if isolate_company and valid_discovered:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM jobs")
                conn.commit()

        ranked_jobs = rank_jobs_by_embedding(valid_discovered, threshold=0.65)
        for j in ranked_jobs:
            save_job(j)
        return {
            "status": "success",
            "message": f"Discovered and evaluated {len(ranked_jobs)} real jobs from {board.capitalize()}. Other jobs removed.",
            "jobs": [j.model_dump() for j in ranked_jobs]
        }

    # Match in local SQLite
    all_jobs = [j for j in list_jobs() if is_real_job(j)]
    matching_local = [
        j for j in all_jobs
        if any(term in j.title.lower() or term in j.description.lower() or term in j.company.lower() for term in query_str.split())
    ]

    if matching_local:
        if isolate_company:
            matched_companies = {j.company.lower() for j in matching_local}
            with get_db_connection() as conn:
                placeholders = ",".join(["?"] * len(matched_companies))
                conn.execute(f"DELETE FROM jobs WHERE LOWER(company) NOT IN ({placeholders})", list(matched_companies))
                conn.commit()

        ranked_jobs = rank_jobs_by_embedding(matching_local, threshold=0.65)
        return {
            "status": "success",
            "message": f"Found {len(ranked_jobs)} jobs matching '{board}'. Other jobs removed.",
            "jobs": [j.model_dump() for j in ranked_jobs]
        }

    fallback_boards = ["cloudflare", "gitlab", "linear", "spotify", "stripe"]
    for fb in fallback_boards:
        jobs = await fetch_jobs_from_any_board(query_token=fb, limit=10)
        for j in jobs:
            if is_real_job(j) and any(term in j.title.lower() or term in j.company.lower() for term in query_str.split()):
                discovered_jobs.append(j)

    if discovered_jobs:
        if isolate_company:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM jobs")
                conn.commit()

        ranked_jobs = rank_jobs_by_embedding(discovered_jobs, threshold=0.65)
        for j in ranked_jobs:
            save_job(j)
        return {
            "status": "success",
            "message": f"Discovered {len(ranked_jobs)} jobs matching '{board}' from live multi-ATS boards.",
            "jobs": [j.model_dump() for j in ranked_jobs]
        }

    return {
        "status": "warning",
        "message": f"No active jobs found for '{board}'. Tip: Try Greenhouse ('cloudflare', 'gitlab', 'stripe'), Ashby ('linear', 'ramp', 'notion'), or Lever ('spotify', 'rover').",
        "jobs": []
    }


@app.post("/api/jobs/rank")
async def rank_all_jobs():
    """
    Executes 2-stage discovery & ranking across all real jobs in SQLite.
    Stage 1: Dense embedding ranker (BGE-Small)
    Stage 2: LLM reranker with explanation
    """
    jobs = list_jobs()
    valid_jobs = [j for j in jobs if is_real_job(j)]

    if not valid_jobs:
        return {
            "status": "warning",
            "message": "No real jobs found in database. Search a company board first.",
            "ranked_jobs": []
        }

    stg1_survivors = rank_jobs_by_embedding(valid_jobs, threshold=0.40)

    results = []
    for job in stg1_survivors:
        eval_result = await evaluate_job_with_llm(job)
        job.llm_score = eval_result.match_score
        job.llm_reasoning = f"[{eval_result.verdict}] {eval_result.explanation}"
        
        if job.status not in ["applied", "interview", "offer", "rejected_by_user"]:
            job.status = "matched" if eval_result.match_score >= 60 else "rejected"
            
        save_job(job)
        results.append(job.model_dump())

    return {"status": "success", "ranked_jobs": results}


@app.post("/api/applications/start")
async def start_application(payload: StartApplicationRequest):
    """
    Starts LangGraph application pipeline for any ATS platform.
    Executes: Match -> Tailor -> Fact Audit -> Multi-ATS Form Fill.
    AUTOMATICALLY PAUSES at review checkpoint and returns state for approval.
    """
    job = get_job_by_id(payload.job_id)
    if not job or not is_real_job(job):
        raise HTTPException(status_code=404, detail=f"Job {payload.job_id} not found.")

    try:
        run_result = await start_application_pipeline(payload.job_id)
    except Exception as e:
        error_msg = str(e)
        if "RateLimitError" in type(e).__name__ or "rate_limit" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Groq AI token quota temporarily exceeded. Rotating models automatically; please retry in 30 seconds."
            )
        raise HTTPException(status_code=500, detail=f"Application pipeline error: {error_msg}")

    state = run_result["state"]

    screenshot_url = None
    expected_screenshot = EXPORTS_DIR / f"{payload.job_id}_form_preview.png"
    if state.get("preview_screenshot_path") and Path(state["preview_screenshot_path"]).exists():
        filename = Path(state["preview_screenshot_path"]).name
        screenshot_url = f"/exports/{filename}"
    elif expected_screenshot.exists():
        screenshot_url = f"/exports/{expected_screenshot.name}"

    resume_data = state["tailored_resume"].model_dump() if state.get("tailored_resume") else None
    cover_letter_data = state["tailored_cover_letter"].model_dump() if state.get("tailored_cover_letter") else None
    audit_data = state["audit_report"].model_dump() if state.get("audit_report") else None
    match_data = state["match_evaluation"].model_dump() if state.get("match_evaluation") else None

    app_url = state.get("application_url")
    if not app_url or "test_form.html" in str(app_url) or not str(app_url).startswith("http"):
        app_url = "/test-form"

    return {
        "status": "paused_for_approval",
        "thread_id": run_result["thread_id"],
        "next_node": run_result["next_node"],
        "job": job.model_dump(),
        "application_url": app_url,
        "screenshot_url": screenshot_url,
        "match_evaluation": match_data,
        "audit_report": audit_data,
        "tailored_resume": resume_data,
        "tailored_cover_letter": cover_letter_data,
        "workflow_status": state.get("workflow_status"),
        "logs": state.get("logs", [])
    }


@app.post("/api/applications/decide")
async def decide_application(payload: DecisionRequest):
    """
    Resumes LangGraph execution after human decision:
    - Approve: marks applied and updates DB.
    - Reject: logs feedback and marks rejected_by_user.
    """
    result = await resume_with_human_decision(
        thread_id=payload.thread_id,
        approve=payload.approve,
        feedback=payload.feedback or ""
    )
    return result


@app.post("/api/applications/open-browser")
async def open_live_browser(payload: OpenBrowserRequest):
    """
    Explicitly launches or foregrounds a live headed Chromium browser window
    for the selected job application, allowing direct interactive review.
    """
    ensure_default_desktop()
    job = get_job_by_id(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    target_url = job.url or LOCAL_TEST_FORM_URL
    if not str(target_url).startswith("http"):
        target_url = LOCAL_TEST_FORM_URL

    existing_bm = ACTIVE_BROWSERS.get(payload.job_id)
    if existing_bm and existing_bm.is_open():
        await existing_bm.bring_to_front()
        return {
            "status": "success",
            "message": "Live Chromium window brought to foreground on your desktop.",
            "url": target_url
        }

    bm = BrowserManager(headless=False)
    page = await bm.start()
    await bm.goto(target_url)
    ACTIVE_BROWSERS[payload.job_id] = bm

    return {
        "status": "success",
        "message": "Live Chromium window opened visibly on your desktop.",
        "url": target_url
    }


# Serve built frontend single-page application if dist exists
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

