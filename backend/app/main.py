"""
main.py — HITL Exam Grading Server
FastAPI entry point. Handles app creation, middleware, DB lifespan,
and router registration. Run with:
    uvicorn app.main:app --reload
(run from the GradeOps/backend/ directory)
"""

from dotenv import load_dotenv
load_dotenv()  # reads GradeOps/backend/.env before any os.getenv() calls

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import time

# ── Database layer ────────────────────────────────────────────────────────────
from app.database.postgres import engine, Base
from app.database.mongo import connect_mongo, close_mongo

# ── Routers (uncomment each one as you build it) ──────────────────────────────
from app.routers import auth
from app.routers import exams, questions, grades, reviews, users

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("grader")


# ---------------------------------------------------------------------------
# Lifespan — startup and shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Everything before `yield` runs on startup.
    Everything after `yield` runs on shutdown.
    """
    logger.info("Starting up HITL Grading Server...")

    # 1. Create all PostgreSQL tables (skips existing — safe to call every time)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL tables verified.")
    except Exception as exc:
        logger.error(f"PostgreSQL startup failed: {exc}")
        raise

    # 2. Connect to MongoDB and build indexes
    try:
        await connect_mongo()
        logger.info("MongoDB connected.")
    except Exception as exc:
        logger.error(f"MongoDB startup failed: {exc}")
        raise

    yield  # ← server is live here

    # Shutdown: close both DB connections cleanly
    await close_mongo()
    await engine.dispose()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="HITL Exam Grading API",
    description=(
        "Human-in-the-Loop exam grading pipeline. "
        "Instructors upload exam scans and rubrics. "
        "An agentic LLM pipeline grades answers, and TAs review/approve."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",    # Swagger UI  →  http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc        →  http://localhost:8000/redoc
)


# ---------------------------------------------------------------------------
# CORS — allow the React frontend to talk to this server
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # React (CRA)
        "http://localhost:5173",   # React (Vite)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request timing middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": " → ".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Check server logs."},
    )


# ---------------------------------------------------------------------------
# Routers — uncomment as each router file is placed in app/routers/
# ---------------------------------------------------------------------------
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(users.router,     prefix="/users",     tags=["Users"])
app.include_router(exams.router,     prefix="/exams",     tags=["Exams"])
app.include_router(questions.router, prefix="/questions", tags=["Questions"])
app.include_router(grades.router,    prefix="/grades",    tags=["AI Grades"])
app.include_router(reviews.router,   prefix="/reviews",   tags=["TA Reviews"])


# ---------------------------------------------------------------------------
# Health-check — pings both databases
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"], summary="Server + DB health check")
async def health():
    """
    Returns 200 with DB status.
    Useful for Docker / load-balancer probes.
    """
    from app.database.mongo import _client as mongo_client
    from sqlalchemy import text

    pg_ok, mongo_ok = False, False

    # Ping PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        pg_ok = True
    except Exception:
        pass

    # Ping MongoDB
    try:
        if mongo_client is not None:
            await mongo_client.admin.command("ping")
            mongo_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if (pg_ok and mongo_ok) else "degraded",
        "version": app.version,
        "databases": {
            "postgres": "connected" if pg_ok else "unreachable",
            "mongodb":  "connected" if mongo_ok else "unreachable",
        },
    }


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "HITL Grading API. Visit /docs for the interactive API explorer."}
