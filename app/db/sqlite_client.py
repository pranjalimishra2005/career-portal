import sqlite3
from typing import List, Optional
from app.core.config import settings
from app.db.job_schema import JobPosting


def get_db_connection() -> sqlite3.Connection:
    """Creates a connection to the local SQLite database and enables row dict access."""
    settings.SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database schema if tables do not exist."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                url TEXT NOT NULL,
                description TEXT NOT NULL,
                platform TEXT DEFAULT 'greenhouse',
                embedding_score REAL,
                llm_score REAL,
                llm_reasoning TEXT,
                status TEXT DEFAULT 'discovered',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_job(job: JobPosting):
    """Inserts or updates a job posting."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO jobs (
                id, title, company, location, url, description, platform,
                embedding_score, llm_score, llm_reasoning, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                embedding_score = excluded.embedding_score,
                llm_score = excluded.llm_score,
                llm_reasoning = excluded.llm_reasoning,
                status = excluded.status
        """, (
            job.id, job.title, job.company, job.location, job.url, job.description, job.platform,
            job.embedding_score, job.llm_score, job.llm_reasoning, job.status, job.created_at
        ))
        conn.commit()


def get_job_by_id(job_id: str) -> Optional[JobPosting]:
    """Retrieves a single job by ID."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            return JobPosting(**dict(row))
        return None


def list_jobs(status: Optional[str] = None, limit: int = 50) -> List[JobPosting]:
    """Lists jobs, optionally filtered by status."""
    with get_db_connection() as conn:
        if status:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        return [JobPosting(**dict(row)) for row in cursor.fetchall()]