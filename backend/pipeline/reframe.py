"""
Pipeline Stage 5 — Reframe
For each selected scene, uses OpenCV Haar cascade face detection (lightweight,
no MediaPipe required) to smart-crop to 9:16 vertical, then re-uploads to MinIO.
Creates Clip DB records.

Memory footprint: ~50MB (vs ~500MB with MediaPipe).
"""
import subprocess
import logging
import uuid
from pathlib import Path

import cv2
import numpy as np

from config import settings
from storage.minio_client import download_file, upload_file, clip_key

logger = logging.getLogger(__name__)

PLATFORMS = ["tiktok", "reels", "shorts"]

# Output resolution: 1080x1920 (9:16 vertical)
OUT_W, OUT_H = 1080, 1920

# OpenCV Haar cascade paths
_CASCADES = {
    "frontal": str(cv2.data.haarcascades + "haarcascade_frontalface_default.xml"),
    "profile": str(cv2.data.haarcascades + "haarcascade_profileface.xml"),
    "upperbody": str(cv2.data.haarcascades + "haarcascade_upperbody.xml"),
}
_loaded_cascades = {}


def _get_cascade(name: str):
    global _loaded_cascades
    if name not in _loaded_cascades:
        _loaded_cascades[name] = cv2.CascadeClassifier(_CASCADES[name])
    return _loaded_cascades[name]


def run_reframe(ctx: dict) -> dict:
    job_id = ctx["job_id"]
    db = ctx["db"]
    selected_scene_ids = ctx.get("selected_scene_ids", [])
    processed_obj_key = ctx.get("processed_key")

    if not selected_scene_ids:
        return {**ctx, "clip_ids": []}

    from models import Scene, Clip

    # ── Download transcoded video once ────────────────────────────────
    local_video = settings.temp_path / f"{job_id}_transcoded.mp4"
    if not local_video.exists():
        download_file(processed_obj_key, local_video)

    scenes = db.query(Scene).filter(Scene.id.in_(selected_scene_ids)).all()
    clip_ids = []

    for scene in scenes:
        try:
            crop_x, crop_y, crop_w, crop_h = _compute_crop_box(
                local_video, scene.start_sec, scene.end_sec
            )
            logger.info(
                f"[reframe] scene={scene.scene_index} "
                f"crop=({crop_x},{crop_y},{crop_w}x{crop_h})"
            )

            for platform in PLATFORMS:
                c_id = str(uuid.uuid4())
                local_clip = settings.temp_path / f"{job_id}_{c_id}_{platform}.mp4"

                _cut_and_reframe(
                    local_video, scene.start_sec, scene.end_sec,
                    crop_x, crop_y, crop_w, crop_h, local_clip,
                )

                obj_key = clip_key(job_id, c_id, platform)
                upload_file(str(local_clip), obj_key)
                local_clip.unlink(missing_ok=True)

                clip = Clip(
                    id=c_id,
                    job_id=job_id,
                    scene_id=scene.id,
                    platform=platform,
                    file_path=obj_key,
                    duration_sec=round(scene.end_sec - scene.start_sec, 2),
                    virality_score=scene.virality_score,
                )
                db.add(clip)
                clip_ids.append(c_id)

            db.commit()

        except Exception as e:
            logger.error(f"[reframe] scene {scene.id} failed: {e}", exc_info=True)

    local_video.unlink(missing_ok=True)
    logger.info(f"[reframe] job={job_id} clips_created={len(clip_ids)}")
    return {**ctx, "clip_ids": clip_ids}


def _compute_crop_box(video_path: Path, start_sec: float, end_sec: float):
    """
    Sample 15 frames, run multi-stage detection (Frontal -> Profile -> UpperBody),
    with a Motion-Detection fallback to center on movement.
    """
    cap = cv2.VideoCapture(str(video_path))
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Increase sampling density for better accuracy
    sample_times = np.linspace(start_sec + 0.5, end_sec - 0.5, num=15)
    points_of_interest_x = []
    
    prev_gray = None
    scale = vid_w / 320
    
    for t in sample_times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if not ret:
            continue
            
        # 1. Human Feature Detection
        small = cv2.resize(frame, (320, int(320 * vid_h / vid_w)))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        
        found_x = None
        
        # Try Frontal -> Profile -> UpperBody
        for stage in ["frontal", "profile", "upperbody"]:
            cascade = _get_cascade(stage)
            objs = cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
            if len(objs) > 0:
                # Prioritize largest object
                x, y, w, h = max(objs, key=lambda o: o[2] * o[3])
                found_x = (x + w / 2) * scale
                break
        
        if found_x is not None:
            points_of_interest_x.append(found_x)
        
        # 2. Motion Detection Fallback (if no human found yet)
        elif prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            moments = cv2.moments(thresh)
            if moments["m00"] > 500: # Significant movement
                motion_x = (moments["m10"] / moments["m00"]) * scale
                points_of_interest_x.append(motion_x)
                
        prev_gray = gray

    cap.release()

    # Determine 9:16 crop dimensions
    crop_h = vid_h
    crop_w = int(crop_h * OUT_W / OUT_H)

    if crop_w > vid_w:
        crop_w = vid_w
        crop_h = int(crop_w * OUT_H / OUT_W)

    # Robust centering: use Median X to ignore outliers
    if points_of_interest_x:
        avg_center_x = int(np.median(points_of_interest_x))
    else:
        avg_center_x = vid_w // 2

    # Smooth the center toward the middle slightly if it's too extreme
    # (prevents cutting off side-profile speakers too aggressively)
    actual_center_x = int(0.8 * avg_center_x + 0.2 * (vid_w // 2))

    crop_x = max(0, min(actual_center_x - crop_w // 2, vid_w - crop_w))
    crop_y = max(0, (vid_h - crop_h) // 2)

    return crop_x, crop_y, crop_w, crop_h


def _cut_and_reframe(
    video_path: Path,
    start: float, end: float,
    crop_x: int, crop_y: int, crop_w: int, crop_h: int,
    output_path: Path,
):
    """Cut segment, crop to subject, scale to 1080x1920."""
    duration = end - start
    vf = (
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={OUT_W}:{OUT_H}:flags=lanczos"
    )
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(video_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
