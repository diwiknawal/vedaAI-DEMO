"""
Pipeline Stage 3 — Scene Detection
Downloads transcoded video, uses PySceneDetect ContentDetector to find
scene boundaries, extracts thumbnail for each scene, uploads thumbnails
to MinIO, saves Scene rows to DB.
"""
import subprocess
import logging
from pathlib import Path

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

from config import settings
from storage.minio_client import download_file, upload_file, thumbnail_key

logger = logging.getLogger(__name__)

# Scene must be at least this long (seconds) to be kept
MIN_SCENE_DURATION = 8.0
# Merge adjacent short scenes if combined duration is within clip range
MAX_SCENE_DURATION = 90.0


def run_scene_detect(ctx: dict) -> dict:
    job_id = ctx["job_id"]
    db = ctx["db"]
    processed_obj_key = ctx.get("processed_key")
    transcript = ctx.get("transcript", {})

    # ── Download transcoded video ─────────────────────────────────────
    local_video = settings.temp_path / f"{job_id}_transcoded.mp4"
    if not local_video.exists():
        download_file(processed_obj_key, local_video)

    # ── Run scene detection ───────────────────────────────────────────
    video = open_video(str(local_video))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27.0, min_scene_len=15))
    scene_manager.detect_scenes(video, show_progress=False)
    raw_scenes = scene_manager.get_scene_list()

    logger.info(f"[scene_detect] job={job_id} raw_scenes={len(raw_scenes)}")

    # ── Convert to dicts + filter ─────────────────────────────────────
    scenes = []
    for i, (start, end) in enumerate(raw_scenes):
        start_sec = start.get_seconds()
        end_sec = end.get_seconds()
        duration = end_sec - start_sec
        if duration < MIN_SCENE_DURATION:
            continue
        if duration > MAX_SCENE_DURATION:
            # Split long scenes into ~30-second chunks
            scenes.extend(_split_long_scene(i, start_sec, end_sec))
        else:
            scenes.append({
                "index": i,
                "start_sec": round(start_sec, 3),
                "end_sec": round(end_sec, 3),
                "duration_sec": round(duration, 3),
            })

    # ── Extract thumbnails + enrich with transcript ───────────────────
    words = transcript.get("words", [])
    from models import Scene as SceneModel
    db_scenes = []

    for s in scenes:
        thumb_path = _extract_thumbnail(local_video, s["start_sec"], job_id, s["index"])
        thumb_key = thumbnail_key(job_id, s["index"])
        if thumb_path:
            upload_file(str(thumb_path), thumb_key)
            thumb_path.unlink(missing_ok=True)

        # Segment transcript words that fall within this scene
        segment_words = [
            w["word"] for w in words
            if s["start_sec"] <= w["start"] < s["end_sec"]
        ]
        transcript_segment = " ".join(segment_words)

        scene = SceneModel(
            job_id=job_id,
            scene_index=s["index"],
            start_sec=s["start_sec"],
            end_sec=s["end_sec"],
            duration_sec=s["duration_sec"],
            transcript_segment=transcript_segment,
            thumbnail_path=thumb_key if thumb_path else None,
        )
        db.add(scene)
        db_scenes.append(scene)

    db.commit()
    for s in db_scenes:
        db.refresh(s)

    local_video.unlink(missing_ok=True)

    logger.info(f"[scene_detect] job={job_id} kept_scenes={len(db_scenes)}")
    return {**ctx, "scene_ids": [s.id for s in db_scenes]}


def _extract_thumbnail(video_path: Path, timestamp: float, job_id: str, index: int) -> Path | None:
    out = settings.temp_path / f"{job_id}_thumb_{index}.jpg"
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp + 1.0),  # +1s to avoid black frame at cut
        "-i", str(video_path),
        "-frames:v", "1",
        "-vf", "scale=480:-2",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return out if out.exists() else None
    except Exception as e:
        logger.warning(f"Thumbnail extraction failed for scene {index}: {e}")
        return None


def _split_long_scene(base_index: int, start: float, end: float) -> list[dict]:
    """Chunk a scene longer than MAX_SCENE_DURATION into ~30s pieces."""
    chunks = []
    chunk_size = 30.0
    t = start
    i = 0
    while t < end:
        chunk_end = min(t + chunk_size, end)
        duration = chunk_end - t
        if duration >= MIN_SCENE_DURATION:
            chunks.append({
                "index": int(f"{base_index}{i}"),
                "start_sec": round(t, 3),
                "end_sec": round(chunk_end, 3),
                "duration_sec": round(duration, 3),
            })
        t = chunk_end
        i += 1
    return chunks
