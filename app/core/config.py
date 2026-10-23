from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the repository (ai-job-agent/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Application settings validated against environment variables.
    Reads from .env file automatically.
    """
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    APP_ENV: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    # Storage Paths
    SQLITE_DB_PATH: Path = Field(default=BASE_DIR / "data" / "app.db")
    CHROMA_PERSIST_DIR: Path = Field(default=BASE_DIR / "data" / "chromadb")
    PROFILE_DATA_DIR: Path = Field(default=BASE_DIR / "data" / "profile")

    # Embeddings (lightweight default)
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # LLM Settings
    DEFAULT_LLM_PROVIDER: Literal["gemini", "groq", "ollama"] = "groq"
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Browser Automation (Set to False to pop up a visible Chromium window on your screen)
    HEADLESS_BROWSER: bool = Field(default=False)


# Singleton instance to import across the project
settings = Settings()
