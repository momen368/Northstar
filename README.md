# AI Resume Analyzer

Northstar is a FastAPI and SQLite AI Resume Analyzer with bearer-token authentication, PDF/DOCX extraction, structured resume analysis, owner-scoped job management and matching, semantic RAG, career advice, resume improvements, and a vanilla HTML/CSS/JavaScript interface.

## Requirements

- Python 3.10 or newer
- pip

## Run on Windows PowerShell

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --reload
```

The application runs at `http://127.0.0.1:8000`. The frontend is served from `/`; Swagger UI is at `/docs`, and the OpenAPI schema is at `/openapi.json`.

## Deploy a Demo on Render

The repository includes a `render.yaml` Blueprint. In Render, choose **New + → Blueprint**, connect `momen368/Northstar`, and confirm the resources shown in the Blueprint. The Blueprint runs the FastAPI app, checks `/api/health/database`, and stores the SQLite database and uploaded resumes on a persistent disk at `/var/data`.

The persistent disk requires a paid web service plan; Render's free web services do not support persistent disks. The configured `0.5c-512mb` plan is currently listed at $7/month, and the 1 GB disk at $0.25/month. Review the current [Render pricing](https://render.com/pricing) before creating the Blueprint. Do not choose the free plan for this configuration, because the database and uploaded files would not persist across restarts.

During Blueprint creation, provide `AI_BASE_URL`, `AI_MODEL`, and `AI_API_KEY` in Render's environment-variable prompts. These values are not stored in this repository. Use credentials for an OpenAI-compatible chat-completions endpoint; without valid provider settings, resume analysis, matching explanations, and career advice return controlled errors. After deployment, open the Render URL and check `/api/health/database` before creating user accounts.

This setup is intended for a small demo on a single instance. The SQLite database and uploads share a 1 GB disk; monitor its capacity as user data grows.

The app reads `DATABASE_URL` from `.env`; the default stores `ai_resume_analyzer.db` in the project root. Tables are created automatically on startup. To initialize them explicitly without starting the API, run:

```powershell
python -m backend.init_database
```

The database connectivity check is available at `/api/health/database`.

Authentication endpoints are `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout`. Login returns an opaque bearer token; only its SHA-256 digest is stored in the database. Tokens expire according to `SESSION_TTL_HOURS` and logout revokes the current token.

Resume endpoints require `Authorization: Bearer <access_token>`: `POST /api/resumes/upload`, `GET /api/resumes`, `GET /api/resumes/{resume_id}`, and `DELETE /api/resumes/{resume_id}`. Uploads accept structurally valid PDF or DOCX files, are stored under `UPLOADS_DIR` using generated names, and are limited by `MAX_UPLOAD_SIZE_MB` (10 MB by default). Original filenames are retained only as sanitized display metadata. Successful uploads extract and save normalized text in the resume record; empty or unreadable documents are rejected.

Analyze an owned resume with `POST /api/resumes/{resume_id}/analyze`. Configure `AI_BASE_URL`, `AI_MODEL`, and optional `AI_API_KEY` for an OpenAI-compatible chat-completions endpoint. Analysis output is validated against the structured Pydantic schema before it is stored and returned.

Job endpoints require a bearer token: `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{job_id}`, `PUT /api/jobs/{job_id}`, `DELETE /api/jobs/{job_id}`, and `GET /api/jobs/search`. Jobs are private to their creator; `skills` are normalized and persisted through the `JobSkill` association. Listing and search responses include `items`, `total`, `limit`, and `offset`. Search filters include `keyword`, `location`, `experience_level`, and `skill`.

Job matching uses `POST /api/recommendations/match` with `resume_id` and `job_id`; the latest saved resume analysis is required. Skill/experience/education scoring is deterministic, and the configured chat model writes an evidence-limited explanation. `GET /api/recommendations/{resume_id}` returns saved results sorted by score.

Career advice is available at `POST /api/career-advisor` with `resume_id` and `question`. Resume improvements use `POST /api/resumes/{resume_id}/improve`. Both combine the latest resume analysis with retrieved knowledge. Resource suggestions cite retrieved chunks; when no relevant content is retrieved, unsupported resources are omitted.

## AI And RAG Configuration

Set `AI_BASE_URL`, `AI_MODEL`, and optionally `AI_API_KEY` for an OpenAI-compatible chat-completions endpoint. Set `EMBEDDING_MODEL` for its embeddings endpoint. No credentials are included in source; unset provider settings produce controlled service errors.

Add UTF-8 `.txt`/`.md`, readable PDF, or DOCX reference files under `knowledge_base/jobs/`, `skills/`, `career_roadmaps/`, `learning_resources/`, or `resume_guidelines/`. Ingest and query them with:

```powershell
python -m backend.scripts.rag_demo "Python career roadmap" --ingest
```

RAG uses configurable `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `RAG_TOP_K`, and `RAG_MIN_SIMILARITY`; chunk metadata and embeddings are stored in SQLite.

The frontend pages are `/`, `/login.html`, `/register.html`, `/dashboard.html`, `/resume.html`, `/jobs.html`, `/job-details.html`, and `/advisor.html`. Browser auth tokens are held in `sessionStorage` and sent as bearer authorization headers. The dashboard uses the persisted-analysis read endpoint `GET /api/resumes/{resume_id}/analysis` so it never reruns AI just to render saved results.

Run tests with:

```powershell
pytest backend/tests
```
