# MAJOR PROJECT PROPOSAL

## Autonomous AI Job Application Agent
**An Intelligent Multi-Stage Assistant for Job Discovery, Resume Matching, and Automated Application Submission**

---

## 1. PROJECT OVERVIEW

Finding a tech job today is exhausting and repetitive. Job seekers spend countless hours browsing different job boards, tailoring resumes for each job description, and typing the same personal details into company application forms over and over again.

This **Major Project** builds an **Autonomous AI Job Application Agent** that automates the tedious parts of the job search while keeping the human in full control. 

The system:
1. **Finds real job postings** directly from company hiring systems (like Greenhouse and Lever) and tech job boards.
2. **Evaluates job fit** using a smart two-stage matching process (fast local similarity check + deep AI recruiter evaluation).
3. **Customizes the resume and cover letter** using only real, verified facts from the candidate's background (zero AI hallucination).
4. **Asks the user for approval** before submitting anything.
5. **Automatically fills out the application form** on the company website using browser automation (**Playwright**).

---

## 2. PROBLEM STATEMENT: WHY DO WE NEED THIS?

1. **Repetitive & Time-Consuming:** Applying to 50–100 jobs takes weeks of manual work, mostly copying and pasting identical information into different job portals.
2. **ATS Filtering Problem:** Most companies use Applicant Tracking Systems (ATS). If a resume doesn't highlight the exact keywords and skills listed in the job description, it gets automatically rejected even if the candidate is qualified.
3. **Spam Bots Don't Work:** Existing automation tools blindly blast generic resumes to thousands of random jobs. This results in immediate rejections, account bans, and frustration for both candidates and recruiters.
4. **AI Hallucination Risk:** Many simple ChatGPT tools make up fake experiences or exaggerate skills to match a job. This is dangerous and dishonest. Our system fixes this with strict fact-checking against the user's real profile.

---

## 3. WHERE WILL WE GET JOB LISTINGS FROM?

Instead of relying on fragile web scraping that breaks when websites change their layout, our system collects jobs through clean, reliable channels:

```
+--------------------------------------------------------------------------------+
|                          JOB DATA SOURCES                                      |
+--------------------------------------------------------------------------------+
  │
  ├── 1. Enterprise ATS APIs (Primary Source)
  │    • Greenhouse API: Used by companies like Stripe, Cloudflare, Airbnb, GitHub.
  │      Provides official, live job listings in clean JSON format.
  │    • Lever API: Used by tech scale-ups like Figma and Netflix.
  │    • Ashby API: Used by high-growth AI and tech startups.
  │    *Why:* 100% reliable, zero CAPTCHA issues, and never breaks due to website redesigns.
  │
  ├── 2. Tech Job Board APIs
  │    • RemoteOK API: For verified remote software developer roles.
  │    • Arbeitnow API: For tech positions with clear salary and requirement data.
  │
  └── 3. Browser-Based Job Scraper (Fallback)
       • Playwright crawler to fetch jobs from company career pages that do not have a public API.
```

---

## 4. HOW THE SYSTEM WORKS (STEP-BY-STEP WORKFLOW)

The application follows a simple, 6-step pipeline:

```
[Candidate Profile / Resume]
             │
             ▼
[Step 1: Save Profile to Vector DB] ──► Converts candidate skills & projects into searchable chunks
             │
[Step 2: Fetch Live Jobs]           ──► Ingests clean postings from Greenhouse / Lever / Job APIs
             │
             ▼
[Step 3: Two-Stage Job Matching]
    ├── Stage 3A: Fast Filter       ──► Local embedding model scores similarity (drops poor matches)
    └── Stage 3B: AI Recruiter Check ──► LLM evaluates missing skills, fit score (0-100), and verdict
             │
             ▼
[Step 4: Tailor Resume & Cover Letter] ► Re-orders bullet points & highlights matching skills (no fake info)
             │
             ▼
[Step 5: Human-in-the-Loop Review]   ──► Candidate sees the match on the dashboard and clicks "Approve"
             │
             ▼
[Step 6: Automated Form Submission]  ──► Playwright opens the job page, fills the form, and uploads resume
```

### Explanation of Steps:

- **Step 1: Profile Knowledge Base (RAG):** The user provides their resume, skills, and projects. The system breaks this into chunks and stores it in a local vector database (**ChromaDB**).
- **Step 2: Job Ingestion:** The system pulls live jobs, cleans up messy HTML text, and stores them in an SQLite database.
- **Step 3: Two-Stage Matching Engine:**
  - **Stage A (Local & Fast):** Uses a lightweight local model (`bge-small-en-v1.5`) to compare the job description with the profile. This filters out 80% of irrelevant jobs instantly without spending API credits.
  - **Stage B (Deep AI Evaluation):** For promising jobs, an LLM (Gemini / Groq) acts as a strict recruiter. It checks if the candidate meets core requirements, outputs a score from 0 to 100, and lists matched skills and missing qualifications.
- **Step 4: Tailored Resume & Cover Letter:** The agent drafts a targeted cover letter and highlights relevant projects in `.docx` format, strictly using verified candidate facts.
- **Step 5: Human Review (Dashboard):** The candidate sees the match score, reason, and tailored documents on their React dashboard. The user has the final word to approve or skip.
- **Step 6: Browser Form Filling:** Once approved, **Playwright** launches in the background, visits the application page, fills in text fields (name, email, portfolio, LinkedIn), uploads the customized resume, and completes the submission.

---

## 5. TECHNOLOGY STACK

| Component | Technology | Why We Are Using It |
|---|---|---|
| **Backend API** | **FastAPI (Python 3.11)** | Fast, asynchronous web framework; handles agent tasks and API routes smoothly. |
| **Relational Database** | **SQLite** | Lightweight, local database to track job statuses (`discovered`, `matched`, `applied`). |
| **Vector Database** | **ChromaDB** | Free, local vector database to store and search candidate resume facts. |
| **Local Embeddings** | **Hugging Face `bge-small-en-v1.5`** | Runs on CPU for free; computes mathematical text similarity in milliseconds. |
| **LLM Reasoning** | **Google Gemini Flash / Groq** | Fast, free-tier AI models used for deep recruiter scoring and cover letter generation. |
| **Browser Automation** | **Playwright** | Modern headless browser tool that interacts with web forms, clicks buttons, and uploads files. |
| **Document Generator** | **python-docx** | Generates cleanly formatted `.docx` resumes and cover letters automatically. |
| **Frontend UI** | **React.js + Tailwind CSS** | Clean dashboard for the user to review jobs, inspect match scores, and approve submissions. |
| **Testing** | **pytest** | Ensures reliability of the matching algorithms and data parsers through automated tests. |

---

## 6. KEY ADVANTAGES & INNOVATIONS

1. **No Hallucinations (Grounded RAG):** The AI can only write about projects and skills that actually exist in the candidate's vector profile. It never invents fake experience.
2. **Cost & Speed Efficiency:** Combining local vector embeddings with LLMs means we don't waste API calls on irrelevant jobs.
3. **Safety with Human-in-the-Loop:** Applications are never sent without candidate approval. This guarantees quality and prevents unwanted spam.
4. **Reliable Data Sourcing:** Direct ATS API ingestion avoids fragile HTML scrapers and guarantees accurate job descriptions.

---

## 7. PROJECT ROADMAP & MILESTONES

| Phase | Milestone | Status |
|---|---|---|
| **Phase 1** | Project setup, SQLite database, and configuration modules | **Completed** |
| **Phase 2** | Profile ingestion with local embeddings and ChromaDB vector store | **Completed** |
| **Phase 3** | Resilient LLM connection with structured output and retry loop | **Completed** |
| **Phase 4** | Greenhouse job fetcher and two-stage matching engine | **Completed** |
| **Phase 5** | Resume tailoring engine and cover letter generator (`.docx`) | **In Progress** |
| **Phase 6** | Playwright automated form-filling agent | **Next** |
| **Phase 7** | React frontend dashboard for live monitoring and approvals | **Next** |
| **Phase 8** | End-to-end testing, documentation, and project demonstration | **Final Step** |

---

## 8. EXPECTED PROJECT DELIVERABLES

1. **Backend Application:** A complete FastAPI system that ingests jobs, scores candidate fit, and coordinates agents.
2. **Web Dashboard:** A clean React UI where a student/job seeker can see matched jobs, view why they matched, and approve applications.
3. **Form Automation Script:** A reliable Playwright module that automatically fills standard ATS job applications.
4. **Final Major Project Report & Demo:** Complete source code, test cases, and a live demonstration of an automated application submission.
