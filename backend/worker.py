"""
Veda AI — Celery Worker
Orchestrates the full 7-stage pipeline as a single Celery task.
"""
from celery import Celery
from config import settings

celery_app = Celery(
    "veda",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # Process one video at a time per worker
)


@celery_app.task(bind=True, name="veda.process_video")
def process_video(self, job_id: str):
    """
    Main pipeline task — runs all 7 stages sequentially.
    Progress is updated in the DB after each stage.
    """
    from database import SessionLocal
    from models import Job

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        stages = [
            ("transcoding",       10,  _stage_transcode),
            ("transcribing",      25,  _stage_transcribe),
            ("scene_detecting",   40,  _stage_scene_detect),
            ("virality_scoring",  55,  _stage_virality_score),
            ("reframing",         70,  _stage_reframe),
            ("ai_suggestions",    85,  _stage_ai_suggestions),
            ("captioning",        95,  _stage_caption),
        ]

        context = {"job_id": job_id, "db": db}

        for status, progress, stage_fn in stages:
            job.status = status
            job.progress = progress
            db.commit()
            self.update_state(state="PROGRESS", meta={"status": status, "progress": progress})
            context = stage_fn(context)

        job.status = "completed"
        job.progress = 100
        db.commit()

    except Exception as exc:
        db.query(Job).filter(Job.id == job_id).update({
            "status": "failed",
            "error_message": str(exc),
        })
        db.commit()
        raise
    finally:
        db.close()

    return {"job_id": job_id, "status": "completed"}


# ── Stage wrappers ─────────────────────────────────────────────────────────────

def _stage_transcode(ctx: dict) -> dict:
    from pipeline.transcode import run_transcode
    return run_transcode(ctx)

def _stage_transcribe(ctx: dict) -> dict:
    from pipeline.transcribe import run_transcribe
    return run_transcribe(ctx)

def _stage_scene_detect(ctx: dict) -> dict:
    from pipeline.scene_detect import run_scene_detect
    return run_scene_detect(ctx)

def _stage_virality_score(ctx: dict) -> dict:
    from pipeline.virality_score import run_virality_score
    return run_virality_score(ctx)

def _stage_reframe(ctx: dict) -> dict:
    from pipeline.reframe import run_reframe
    return run_reframe(ctx)

def _stage_ai_suggestions(ctx: dict) -> dict:
    from pipeline.ai_suggestions import run_ai_suggestions
    return run_ai_suggestions(ctx)

def _stage_caption(ctx: dict) -> dict:
    from pipeline.caption import run_caption
    return run_caption(ctx)
