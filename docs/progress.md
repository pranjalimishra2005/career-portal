# AI Job Application Agent - Build Log

## Phase 0: Project Setup
- **Built**: Project folder structure initialized with FastAPI backend and React frontend.
- **Decisions Made**: Decided on React (JavaScript) for the UI for a decoupled client-server architecture.
- **Issues Faced**: None.

## Phase 0: Project Setup
- **What was built**: Initialized the project skeleton, Python 3.11 virtual environment, requirements.txt, .gitignore, and Pydantic Settings configuration module.
- **Key decisions**: Selected a decoupled architecture with FastAPI backend and React frontend; configured local embeddings (BGE-Small) and free LLM providers (Gemini/Groq).
- **Issues faced & fixes**: Handled Windows PowerShell script execution policy bypass for venv activation.

## Phase 2: LLM Interface & Structured Output
- **What was built**: `BaseLLMProvider` abstract contract, concrete `GeminiProvider` using `gemini-flash-latest`, self-correcting validation retry loop, and `get_llm_provider()` factory.
- **Key decisions**: Used strict Pydantic JSON schemas with automated error feedback to guarantee structured responses from free LLM tiers without conversational chatter.
- **Issues faced & fixes**: Handled Google SDK deprecation warnings; identified working model alias (`gemini-flash-latest`) for the active API key; tested async coroutines with `pytest-asyncio`.


## Phase 3: Job Discovery & Matching
- **What was built**: `JobPosting` schema with SQLite persistence (`app.db`), ATS HTML description cleaner, Stage 1 embedding pre-filter (BGE-Small), and Stage 2 LLM reranker with structured Pydantic verdicts.
- **Key decisions**: Implemented a two-stage funnel (fast local cosine pre-filter eliminates mismatches; LLM reranks surviving jobs with reasons); added dual LLM provider support (Gemini + Groq) to handle daily API quota caps.
- **Issues faced & fixes**: Handled Google AI Studio daily free-tier quota exhaustion by integrating Groq (`openai/gpt-oss-20b`); refactored unit tests from static role assertions to dynamic relative overlap scoring.

## Phase 4: MCP Servers
- **What was built**: `profile-rag-server` and `job-search-server` using official Python MCP SDK (FastMCP), exposing semantic search, FAQ answers, job details, and matching tools over JSON-RPC.
- **Key decisions**: Pinned `mcp<2` for stable FastMCP tool decorators; cached ChromaDB and embedding singletons; configured single-threaded execution (`torch.set_num_threads(1)`) to prevent Windows OpenMP deadlocks.
- **Issues faced & fixes**: Diagnosed Windows asynchronous pipe buffer deadlock when subprocess stderr was captured by pytest; fixed by adding `addopts = -s` to `pytest.ini` and silencing library progress bars.

## Phase 5: Tailoring & Claim Verifier
- **What was built**: Role-tailored resume and cover letter generator with source chunk citation, adversarial claim verifier checking atomic assertions against ChromaDB facts, and a Harvard/Jake's format ATS `.docx` and Markdown exporter.
- **Key decisions**: Implemented direct chunk citation verification (`collection.get(ids=[chunk_id])`) to prevent metric mismatches; enforced a zero-tolerance policy where any unsupported claim fails the audit; designed a 0.5" margin Word template with borderless table alignments.
- **Issues faced & fixes**: Handled false-positive metric rejections by prioritizing direct cited chunk lookups over blind vector search; handled Windows file locking (`PermissionError [Errno 13]`) when `.docx` files are open in Word.

## Phase 6: Playwright Basics & Field Detection
- **What was built**: Playwright browser manager controlling Chromium (headed/headless), intelligent DOM field detector classifying 9 standard ATS input types, automated form filler with RAG question answering, and preview screenshot capture.
- **Key decisions**: Built a local mock ATS form (`data/test_form.html`) mirroring Greenhouse/Lever for reliable offline testing; enforced a strict safety stop leaving the submit button untouched.
- **Issues faced & fixes**: Handled PowerShell multi-line quote parsing by creating standalone test runners (`verify_fields.py`, `verify_form_filler.py`); verified native file upload (`set_input_files`) without OS dialogs.

## Phase 7: ATS Form-Fill Agent & Safety Guardrails
- **What was built**: Greenhouse ATS form-fill adapter, security guard detecting CAPTCHAs/Cloudflare/login-walls, and confidence-based handoff module for screening questions with full automated test coverage (`tests/test_greenhouse_agent.py`).
- **Key decisions**: Enforced a strict non-bypass rule (automation immediately halts on bot challenges); engineered a confidence threshold (0.55) with Pydantic structured decisions so the agent never guesses on missing facts; generated preview screenshots while keeping submit button untouched.
- **Issues faced & fixes**: Resolved single-chunk context blindspots by querying multi-chunk RAG evidence; replaced brittle substring matching with strict `ScreeningAnswerDecision` models to prevent false-positive handoffs.

## Phase 8: LangGraph Orchestration & Human Approval
- **What was built**: End-to-end LangGraph state machine (`AgentState`) coordinating profile loading, 2-stage matching, tailoring, adversarial claim audit, Playwright form filling, and human approval resume/reject hooks.
- **Key decisions**: Compiled graph with `interrupt_before=["submit_application"]` and `MemorySaver` checkpointer; enforced a hard safety guard in `submit_node` raising `PermissionError` if `human_approved` is False; added adaptive 429 rate-limit backoff to `GroqProvider`.
- **Issues faced & fixes**: Handled Groq free-tier 8k TPM rate limits with regex delay extraction and `asyncio.sleep()`; added `HEADLESS_BROWSER=false` mode keeping the live Chromium window open on screen for interactive inspection alongside direct form links.