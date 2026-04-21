"""
Pipeline Stage 1 — Transcode
Downloads original from MinIO, transcodes to H.264 1080p/30fps via FFmpeg,
uploads result back to MinIO.
"""
import subprocess
import json
import logging
from pathlib import Path

from config import settings
from storage.minio_client import download_file, upload_file, processed_key

logger = logging.getLogger(__name__)


def run_transcode(ctx: dict) -> dict:
    job_id = ctx["job_id"]
    db = ctx["db"]

    from models import Job
    job = db.query(Job).filter(Job.id == job_id).first()

    # ── Download original from MinIO ──────────────────────────────────
    ext = job.upload_path.rsplit(".", 1)[-1]
    local_input = settings.temp_path / f"{job_id}_input.{ext}"
    download_file(job.upload_path, local_input)

    # ── Probe duration ────────────────────────────────────────────────
    duration = _probe_duration(local_input)
    job.duration_sec = duration
    db.commit()

    # ── Transcode ─────────────────────────────────────────────────────
    local_output = settings.temp_path / f"{job_id}_transcoded.mp4"
    _transcode(local_input, local_output)

    # ── Upload transcoded to MinIO ────────────────────────────────────
    obj_key = processed_key(job_id)
    upload_file(str(local_output), obj_key)

    job.processed_path = obj_key
    db.commit()

    # ── Cleanup ───────────────────────────────────────────────────────
    local_input.unlink(missing_ok=True)
    local_output.unlink(missing_ok=True)

    logger.info(f"[transcode] job={job_id} done, duration={duration:.1f}s")
    return {**ctx, "processed_key": obj_key, "duration_sec": duration}


def _probe_duration(path: Path) -> float:
    """Use ffprobe to get video duration in seconds."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return float(data["format"].get("duration", 0))


def _transcode(input_path: Path, output_path: Path):
    """
    Transcode to H.264, AAC, 1080p max, 30fps.
    Uses -vf scale to preserve AR while fitting within 1920x1080.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1080,ih))',fps=30",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
