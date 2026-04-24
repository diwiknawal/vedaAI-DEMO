"""
Veda AI — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from database import init_db
from storage.minio_client import ensure_bucket
from routers import upload, jobs, clips


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.ensure_dirs()
    init_db()
    ensure_bucket()
    yield
    # Shutdown (nothing to clean up for now)


app = FastAPI(
    title="Veda AI",
    description="Automated short-form video clipping pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(clips.router, prefix="/api", tags=["clips"])




@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
