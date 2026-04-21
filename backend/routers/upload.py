"""
Veda AI — Upload Router
POST /api/upload — streams video to MinIO, creates Job, enqueues pipeline
"""
import uuid
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Job
from config import settings
from storage.minio_client import ensure_bucket, upload_file, upload_key
from worker import process_video

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm", "video/mpeg",
}

EXTENSION_MAP = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/x-matroska": "mkv",
    "video/webm": "webm",
    "video/mpeg": "mpeg",
}


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # ── Validate content type ─────────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Accepted: mp4, mov, avi, mkv, webm",
        )

    job_id = str(uuid.uuid4())
    ext = EXTENSION_MAP.get(file.content_type, "mp4")
    object_key = upload_key(job_id, ext)

    # ── Stream upload → temp file → MinIO ────────────────────────────
    # We buffer to disk first so FFmpeg can work on it inside the worker
    settings.temp_path.mkdir(parents=True, exist_ok=True)
    tmp_path = settings.temp_path / f"{job_id}_upload.{ext}"

    try:
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                f.write(chunk)

        ensure_bucket()
        upload_file(str(tmp_path), object_key)

    finally:
        # Clean up temp file after upload to MinIO
        if tmp_path.exists():
            tmp_path.unlink()

    # ── Create DB Job record ──────────────────────────────────────────
    job = Job(
        id=job_id,
        original_filename=file.filename,
        upload_path=object_key,      # MinIO object key
        status="queued",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # ── Enqueue Celery pipeline task ──────────────────────────────────
    process_video.apply_async(args=[job_id], task_id=job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Video uploaded to storage. Processing pipeline started.",
    }
