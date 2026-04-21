"""
Veda AI — Clips Router
GET /api/clips/{job_id}                           — list clips for a job
GET /api/clips/{job_id}/{clip_id}/url             — presigned MinIO download URL
DELETE /api/clips/{job_id}/{clip_id}              — remove a clip
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Clip, Job
from storage.minio_client import get_presigned_url, delete_object

router = APIRouter()


@router.get("/clips/{job_id}")
def list_clips(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    clips = db.query(Clip).filter(Clip.job_id == job_id).all()
    result = []
    for clip in clips:
        clip_data = clip.to_dict()
        # Generate a short-lived presigned URL for the frontend player
        if clip.file_path:
            try:
                clip_data["download_url"] = get_presigned_url(clip.file_path, expires_in=3600)
            except Exception:
                clip_data["download_url"] = None
        result.append(clip_data)

    return {"clips": result, "total": len(result)}


@router.get("/clips/{job_id}/{clip_id}/url")
def get_clip_url(job_id: str, clip_id: str, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id, Clip.job_id == job_id).first()
    if not clip or not clip.file_path:
        raise HTTPException(status_code=404, detail="Clip not found")
    url = get_presigned_url(clip.file_path, expires_in=3600)
    return {"clip_id": clip_id, "url": url, "expires_in": 3600}


@router.delete("/clips/{job_id}/{clip_id}")
def delete_clip(job_id: str, clip_id: str, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id, Clip.job_id == job_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if clip.file_path:
        delete_object(clip.file_path)
    db.delete(clip)
    db.commit()
    return {"message": "Clip deleted"}
