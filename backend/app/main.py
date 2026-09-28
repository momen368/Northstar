from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request

from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.career_advisor import router as career_advisor_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.resumes import router as resumes_router
from backend.app.api.routes.recommendations import router as recommendations_router
from backend.app.core.config import settings
from backend.app.database.initialization import initialize_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
	initialize_database()
	yield


app = FastAPI(title="AI Resume Analyzer API", version="0.2.0", lifespan=lifespan)
if settings.frontend_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(recommendations_router)
app.include_router(career_advisor_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
	safe_errors = [
		{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
		for error in exc.errors()
	]
	return JSONResponse(status_code=422, content={"detail": safe_errors})


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[2] / "frontend", html=True), name="frontend")
