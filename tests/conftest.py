import json
import shutil
from pathlib import Path
import pytest

from app.core.config import settings, BASE_DIR
from app.db.sqlite_client import init_db
from app.db.profile_schema import UserProfile
from app.db.chunker import chunk_profile
import app.db.vector_store as vs


@pytest.fixture(scope="session", autouse=True)
def isolate_test_environment(tmp_path_factory):
    """
    Session-wide fixture that redirects SQLite, ChromaDB, and Profile directories
    to a temporary sandbox directory during pytest execution.
    
    GUARANTEES:
    1. Tests NEVER overwrite or modify production data/app.db.
    2. Tests NEVER overwrite or modify production data/profile/profile.json.
    3. Tests NEVER pollute production ChromaDB vector facts with mock candidates.
    """
    # 1. Create temporary sandbox directory for test run
    temp_dir = tmp_path_factory.mktemp("agent_test_sandbox")
    test_db = temp_dir / "test_app.db"
    test_chroma = temp_dir / "test_chromadb"
    test_profile_dir = temp_dir / "profile"
    test_profile_dir.mkdir(parents=True, exist_ok=True)

    # 2. Save original production paths
    orig_db = settings.SQLITE_DB_PATH
    orig_chroma = settings.CHROMA_PERSIST_DIR
    orig_profile = settings.PROFILE_DATA_DIR

    # 3. If a production profile exists, copy to sandbox
    prod_profile_file = orig_profile / "profile.json"
    if prod_profile_file.exists():
        shutil.copy(prod_profile_file, test_profile_dir / "profile.json")

    # 4. Redirect settings to the temporary sandbox
    settings.SQLITE_DB_PATH = test_db
    settings.CHROMA_PERSIST_DIR = test_chroma
    settings.PROFILE_DATA_DIR = test_profile_dir

    # 5. Reset singletons so ChromaDB connects to test_chroma
    vs._chroma_client = None
    vs._embedding_function = None
    vs._profile_collection = None

    # 6. Initialize schema in the test database
    init_db()

    # 7. Seed test vector store from sandbox profile
    sandbox_profile_file = test_profile_dir / "profile.json"
    if sandbox_profile_file.exists():
        try:
            with open(sandbox_profile_file, "r", encoding="utf-8") as f:
                prof = UserProfile(**json.load(f))
            chunks = chunk_profile(prof)
            vs.index_profile_chunks(chunks)
        except Exception:
            pass

    yield temp_dir

    # 8. Teardown: Restore original production paths & reset singletons
    settings.SQLITE_DB_PATH = orig_db
    settings.CHROMA_PERSIST_DIR = orig_chroma
    settings.PROFILE_DATA_DIR = orig_profile

    vs._chroma_client = None
    vs._embedding_function = None
    vs._profile_collection = None