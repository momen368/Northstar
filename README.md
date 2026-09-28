# Northstar

Northstar is an AI resume analyzer with bearer-token authentication, PDF/DOCX extraction, structured resume analysis, owner-scoped job management and matching, semantic retrieval, career advice, resume improvements, and a vanilla HTML/CSS/JavaScript interface. SQLite is used locally; the API also supports PostgreSQL deployments.

## Run locally

Requirements: Python 3.10 or newer and pip.

From the project root in Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --reload
```

The app runs at `http://127.0.0.1:8000`. FastAPI serves the frontend at `/`; Swagger UI is at `/docs`. The local SQLite database is `ai_resume_analyzer.db` by default.

## Deploy the frontend on Vercel

The frontend is plain HTML, CSS, and browser JavaScript in `frontend/`. It does not use React, Next.js, or Vite. Import the GitHub repository into Vercel with:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Other |
| Install Command | `npm install` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Rewrites | None |

Set `NORTHSTAR_API_BASE_URL` to the public HTTPS origin of the separately hosted FastAPI backend, for example `https://northstar-api.example.com`. This URL is public configuration, not a secret. The build rejects a missing API URL on Vercel and rejects localhost URLs. Existing routes are individual static HTML files such as `/login.html` and `/dashboard.html`, so no SPA rewrite is needed.

Vercel hosts only the static frontend. The FastAPI API and database run separately. `render.yaml` prepares a no-cost Render Free API service; connect it to a PostgreSQL provider and set `DATABASE_URL` in Render. Add the exact Vercel production origin to the backend's `FRONTEND_ORIGINS` variable to allow browser API requests. Restart the backend after changing it.

Render Free services sleep when idle and use temporary local filesystems. The database must be external (for example, Neon Free); account records and extracted resume text persist in that database, while original uploaded PDF/DOCX files are not durable on this free service. Keep external services within their free quotas.

AI actions require an OpenAI-compatible provider configured on the backend with `AI_BASE_URL`, `AI_MODEL`, and optionally `AI_API_KEY`. No credentials belong in this repository. Review the provider's privacy terms before sending real CVs; some free API tiers use submitted content to improve provider products.

## Environment variables

Copy `.env.example` to `.env` for local development. Important settings:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy database URL; SQLite locally, PostgreSQL for hosted API |
| `FRONTEND_ORIGINS` | Comma-separated exact origins allowed by the API's CORS policy |
| `UPLOADS_DIR` | Directory used for uploaded PDF/DOCX files |
| `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` | Optional OpenAI-compatible chat-completions provider |
| `EMBEDDING_MODEL` | Optional embeddings endpoint model for RAG |

Never commit `.env` or provider credentials. Vercel's `NORTHSTAR_API_BASE_URL` configures only the browser's public API origin; it is not an API key.

## API and user flows

Auth endpoints are `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout`. Login returns an opaque bearer token; only its SHA-256 digest is stored. Tokens expire according to `SESSION_TTL_HOURS`.

Resume endpoints require `Authorization: Bearer <access_token>`: `POST /api/resumes/upload`, `GET /api/resumes`, `GET /api/resumes/{resume_id}`, `DELETE /api/resumes/{resume_id}`, `POST /api/resumes/{resume_id}/analyze`, and `POST /api/resumes/{resume_id}/improve`. Uploads accept validated PDF/DOCX files up to `MAX_UPLOAD_SIZE_MB`; extracted text is saved with the resume record.

Jobs support create/list/read/update/delete and search via `/api/jobs`. Matching uses `POST /api/recommendations/match` and saved results are listed by `GET /api/recommendations/{resume_id}`. Career advice uses `POST /api/career-advisor`. Health checks are `/api/health` and `/api/health/database`.

The frontend pages are `/`, `/login.html`, `/register.html`, `/dashboard.html`, `/resume.html`, `/jobs.html`, `/job-details.html`, and `/advisor.html`. Browser tokens are held in `sessionStorage` and sent as bearer headers.

## Knowledge base

Add UTF-8 `.txt`/`.md`, readable PDF, or DOCX reference files under `knowledge_base/jobs/`, `skills/`, `career_roadmaps/`, `learning_resources/`, or `resume_guidelines/`. Ingest and query locally with:

```powershell
python -m backend.scripts.rag_demo "Python career roadmap" --ingest
```

RAG chunk metadata and embeddings are stored in the configured database.

## Build and test

Build the Vercel frontend from `frontend/`:

```powershell
npm run build
```

Run backend tests from the project root:

```powershell
pytest backend/tests
```
