import re
import html
from html.parser import HTMLParser
from typing import List, Optional
import httpx

from app.db.job_schema import JobPosting
from app.db.sqlite_client import save_job


class HTMLTextStripper(HTMLParser):
    """Cleanly extracts visible text from raw HTML without external bloat."""
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def clean_job_description(raw_content: str) -> str:
    """
    Normalizes any messy job description:
    1. Unescapes HTML entities (&amp;, &nbsp;, &lt;)
    2. Strips HTML tags (<p>, <ul>, <div>, etc.)
    3. Collapses excessive newlines and whitespace into clean readable text
    """
    if not raw_content:
        return ""

    unescaped = html.unescape(raw_content)
    stripper = HTMLTextStripper()
    stripper.feed(unescaped)
    plain_text = stripper.get_text()

    cleaned = re.sub(r"[ \t]+", " ", plain_text)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()


async def fetch_greenhouse_jobs(board_token: str, limit: int = 5) -> List[JobPosting]:
    """
    Fetches real listings from a public Greenhouse board (e.g. 'cloudflare', 'stripe', 'gitlab', 'figma').
    Endpoint: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token.strip().lower()}/jobs?content=true"
    discovered_jobs: List[JobPosting] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return discovered_jobs

            data = response.json()
            jobs_list = data.get("jobs", [])[:limit]

            for item in jobs_list:
                cleaned_desc = clean_job_description(item.get("content", ""))
                location_name = item.get("location", {}).get("name", "Remote")

                job = JobPosting(
                    id=f"gh_{item['id']}",
                    title=item.get("title", "Unknown Role"),
                    company=board_token.capitalize(),
                    location=location_name,
                    url=item.get("absolute_url", ""),
                    description=cleaned_desc,
                    platform="greenhouse",
                    status="discovered"
                )
                save_job(job)
                discovered_jobs.append(job)

    except Exception as e:
        print(f"[JobFetcher] Error fetching from Greenhouse ({board_token}): {e}")

    return discovered_jobs


async def fetch_lever_jobs(company: str, limit: int = 5) -> List[JobPosting]:
    """
    Fetches real listings from a public Lever board (e.g. 'spotify', 'rover').
    Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
    """
    url = f"https://api.lever.co/v0/postings/{company.strip().lower()}?mode=json"
    discovered_jobs: List[JobPosting] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return discovered_jobs

            data = response.json()
            if not isinstance(data, list):
                return discovered_jobs

            for item in data[:limit]:
                raw_desc = item.get("descriptionPlain") or item.get("descriptionBodyPlain") or ""
                if not raw_desc:
                    raw_desc = clean_job_description(item.get("description", ""))

                categories = item.get("categories", {})
                location_name = categories.get("location") or "Remote"

                job = JobPosting(
                    id=f"lever_{item['id']}",
                    title=item.get("text", "Unknown Role"),
                    company=company.capitalize(),
                    location=location_name,
                    url=item.get("applyUrl") or item.get("hostedUrl") or "",
                    description=raw_desc.strip(),
                    platform="lever",
                    status="discovered"
                )
                save_job(job)
                discovered_jobs.append(job)

    except Exception as e:
        print(f"[JobFetcher] Error fetching from Lever ({company}): {e}")

    return discovered_jobs


async def fetch_ashby_jobs(company: str, limit: int = 5) -> List[JobPosting]:
    """
    Fetches real listings from a public Ashby board (e.g. 'linear', 'ramp', 'notion').
    Endpoint: https://api.ashbyhq.com/posting-api/job-board/{company}
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company.strip().lower()}"
    discovered_jobs: List[JobPosting] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return discovered_jobs

            data = response.json()
            jobs_list = data.get("jobs", [])[:limit]

            for item in jobs_list:
                raw_desc = item.get("descriptionPlain") or ""
                if not raw_desc:
                    raw_desc = clean_job_description(item.get("descriptionHtml", ""))

                location_name = item.get("location") or "Remote"
                apply_url = item.get("applyUrl") or item.get("jobUrl") or ""

                job = JobPosting(
                    id=f"ashby_{item['id']}",
                    title=item.get("title", "Unknown Role"),
                    company=company.capitalize(),
                    location=location_name,
                    url=apply_url,
                    description=raw_desc.strip(),
                    platform="ashby",
                    status="discovered"
                )
                save_job(job)
                discovered_jobs.append(job)

    except Exception as e:
        print(f"[JobFetcher] Error fetching from Ashby ({company}): {e}")

    return discovered_jobs


async def fetch_jobs_from_any_board(query_token: str, limit: int = 6) -> List[JobPosting]:
    """
    Unified multi-ATS fetcher: checks Greenhouse, Ashby, and Lever in sequence
    and returns discovered real roles from whichever platform hosts the company.
    """
    token = query_token.strip().lower()

    # 1. Try Greenhouse
    gh_jobs = await fetch_greenhouse_jobs(token, limit=limit)
    if gh_jobs:
        return gh_jobs

    # 2. Try Ashby (Linear, Notion, Ramp, etc.)
    ashby_jobs = await fetch_ashby_jobs(token, limit=limit)
    if ashby_jobs:
        return ashby_jobs

    # 3. Try Lever (Spotify, Rover, etc.)
    lever_jobs = await fetch_lever_jobs(token, limit=limit)
    if lever_jobs:
        return lever_jobs

    return []


def get_sample_jobs(save_to_db: bool = False) -> List[JobPosting]:
    """
    Provides curated offline mock jobs strictly for testing and unit benchmarks.
    Does NOT save to SQLite unless save_to_db=True is explicitly passed by a test fixture.
    """
    sample_data = [
        {
            "id": "sample_backend_01",
            "title": "Junior Python Backend Developer",
            "company": "Nexus Systems",
            "location": "Remote",
            "url": "https://careers.nexussystems.io/jobs/101",
            "description": (
                "About Nexus: We build real-time distributed microservices.\n\n"
                "Requirements:\n"
                "- Strong experience with Python 3 and modern async frameworks (FastAPI or Starlette)\n"
                "- Practical knowledge of relational databases (PostgreSQL) and caching (Redis)\n"
                "- Familiarity with containerization using Docker\n"
                "- Experience writing unit tests with pytest\n"
                "- Degree in Computer Science or equivalent practical experience"
            ),
            "platform": "custom"
        },
        {
            "id": "sample_fullstack_02",
            "title": "Full Stack Engineer (React / Python)",
            "company": "Horizon Apps",
            "location": "San Francisco, CA",
            "url": "https://careers.horizonapps.com/jobs/204",
            "description": (
                "Looking for a Full Stack Engineer to build responsive web interfaces and microservices.\n\n"
                "What You Bring:\n"
                "- Proficiency in React and modern JavaScript/TypeScript\n"
                "- Backend development with Python or Node.js\n"
                "- Familiarity with RESTful API design and database modeling\n"
                "- Collaborative mindset and passion for clean UI"
            ),
            "platform": "custom"
        },
        {
            "id": "sample_mismatch_03",
            "title": "Senior iOS Engineer (Swift)",
            "company": "MobileSwift Labs",
            "location": "New York, NY",
            "url": "https://mobileswift.com/jobs/99",
            "description": (
                "Seeking an experienced iOS engineer.\n\n"
                "Requirements:\n"
                "- 5+ years of production Swift and Objective-C development\n"
                "- Deep expertise in SwiftUI, UIKit, CoreData, and Apple TestFlight deployment\n"
                "- Published at least 3 high-volume iOS apps on the App Store"
            ),
            "platform": "custom"
        }
    ]

    jobs = []
    for data in sample_data:
        job = JobPosting(**data, status="discovered")
        if save_to_db:
            save_job(job)
        jobs.append(job)
    return jobs