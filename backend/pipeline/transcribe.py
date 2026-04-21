"""
Pipeline Stage 2 — Transcribe
Uses faster-whisper (CTranslate2 backend — no PyTorch, ~200MB RAM on tiny model)
instead of openai-whisper, making it viable on 8GB machines.
"""
import json
import logging
from pathlib import Path

from faster_whisper import WhisperModel

from config import settings
from storage.minio_client import download_file, upload_bytes, transcript_key

logger = logging.getLogger(__name__)

# Load model once per worker process and reuse
_model = None

def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        logger.info(f"Loading faster-whisper model: {settings.whisper_model} (CPU, int8)")
        _model = WhisperModel(
            settings.whisper_model,
            device="cpu",
            compute_type="int8",   # int8 quantization — halves RAM vs float32
        )
    return _model


def run_transcribe(ctx: dict) -> dict:
    job_id = ctx["job_id"]
    processed_obj_key = ctx.get("processed_key")

    # ── Download transcoded video ─────────────────────────────────────
    local_video = settings.temp_path / f"{job_id}_transcoded.mp4"
    if not local_video.exists():
        download_file(processed_obj_key, local_video)

    # ── Transcribe with faster-whisper ────────────────────────────────
    model = _get_model()
    segments_iter, info = model.transcribe(
        str(local_video),
        word_timestamps=True,
        vad_filter=True,           # Skip silent sections — saves time
        vad_parameters={"min_silence_duration_ms": 500},
    )

    # ── Materialise the generator + build flat word list ──────────────
    full_text_parts = []
    all_segments = []
    words = []

    for seg in segments_iter:
        full_text_parts.append(seg.text.strip())
        seg_dict = {
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        }
        if seg.words:
            seg_dict["words"] = [
                {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
                for w in seg.words
            ]
            words.extend(seg_dict["words"])
        all_segments.append(seg_dict)

    transcript_data = {
        "text": " ".join(full_text_parts),
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "segments": all_segments,
        "words": words,
    }

    # ── Upload transcript JSON to MinIO ───────────────────────────────
    obj_key = transcript_key(job_id)
    upload_bytes(
        json.dumps(transcript_data, ensure_ascii=False, indent=2).encode(),
        obj_key,
        content_type="application/json",
    )

    local_video.unlink(missing_ok=True)

    logger.info(
        f"[transcribe] job={job_id} words={len(words)} "
        f"lang={info.language} ({info.language_probability:.0%})"
    )
    return {**ctx, "transcript_key": obj_key, "transcript": transcript_data}
