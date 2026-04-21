"""
Pipeline Stage 7 — Caption
Generates TikTok-style animated word-highlight captions using FFmpeg's
drawtext filter. Burns captions directly onto each clip and re-uploads to MinIO.
"""
import subprocess
import logging
import json
import tempfile
from pathlib import Path

from config import settings
from storage.minio_client import download_file, upload_file

logger = logging.getLogger(__name__)

# Caption style constants
FONT_SIZE = 72
FONT_COLOR = "white"
HIGHLIGHT_COLOR = "yellow"
SHADOW_COLOR = "black@0.6"
BOX_COLOR = "black@0.3"
LINE_MAX_CHARS = 22   # Max chars per caption line


def run_caption(ctx: dict) -> dict:
    job_id = ctx["job_id"]
    db = ctx["db"]
    clip_ids = ctx.get("clip_ids", [])
    transcript = ctx.get("transcript", {})

    if not clip_ids:
        return ctx

    from models import Clip, Scene

    clips = db.query(Clip).filter(Clip.id.in_(clip_ids)).all()
    words = transcript.get("words", [])

    for clip in clips:
        try:
            # Skip duplicates (same scene processed for each platform)
            if clip.caption_file:
                continue

            scene = db.query(Scene).filter(Scene.id == clip.scene_id).first()
            if not scene:
                continue

            # Filter words that belong to this scene's time range
            scene_words = [
                w for w in words
                if scene.start_sec <= w["start"] < scene.end_sec
            ]
            # Re-zero timestamps relative to clip start
            relative_words = [
                {
                    "word": w["word"],
                    "start": round(w["start"] - scene.start_sec, 3),
                    "end": round(w["end"] - scene.start_sec, 3),
                }
                for w in scene_words
            ]

            if not relative_words:
                logger.warning(f"[caption] clip={clip.id} no words — skipping captions")
                continue

            # Download raw clip from MinIO
            local_clip_in = settings.temp_path / f"{clip.id}_raw.mp4"
            local_clip_out = settings.temp_path / f"{clip.id}_captioned.mp4"
            download_file(clip.file_path, local_clip_in)

            # Generate ASS subtitle file
            ass_path = settings.temp_path / f"{clip.id}.ass"
            _write_ass(relative_words, ass_path)

            # Burn captions in
            _burn_captions(local_clip_in, ass_path, local_clip_out)

            # Re-upload captioned clip (overwrite original key)
            upload_file(str(local_clip_out), clip.file_path)

            caption_key = clip.file_path.replace(".mp4", ".ass")
            upload_file(str(ass_path), caption_key)
            clip.caption_file = caption_key
            db.commit()

            # Cleanup
            for f in [local_clip_in, local_clip_out, ass_path]:
                f.unlink(missing_ok=True)

            logger.debug(f"[caption] clip={clip.id} ✓")

        except Exception as e:
            logger.error(f"[caption] clip {clip.id} failed: {e}", exc_info=True)

    logger.info(f"[caption] job={job_id} clips_captioned={len(clips)}")
    return ctx


def _write_ass(words: list[dict], path: Path):
    """Generate an ASS subtitle file with word-by-word highlight animation."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(size=FONT_SIZE)

    events = []
    # Group words into lines (~LINE_MAX_CHARS chars)
    lines = _group_words_into_lines(words)

    for line in lines:
        if not line:
            continue
        line_start = line[0]["start"]
        line_end = line[-1]["end"]
        # Build the line text with per-word highlight using {\c} color tags
        for word_item in line:
            ws = word_item["start"]
            we = word_item["end"]
            # Build dialogue line that highlights this word
            line_text = ""
            for w in line:
                if w is word_item:
                    line_text += r"{\c&H00FFFF&}" + w["word"] + r"{\c&HFFFFFF&} "
                else:
                    line_text += w["word"] + " "
            events.append(
                f"Dialogue: 0,{_ts(ws)},{_ts(we)},Default,,0,0,0,,"
                f"{line_text.strip()}"
            )

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))


def _group_words_into_lines(words: list[dict]) -> list[list[dict]]:
    lines = []
    current_line = []
    current_len = 0
    for w in words:
        word_len = len(w["word"]) + 1
        if current_len + word_len > LINE_MAX_CHARS and current_line:
            lines.append(current_line)
            current_line = [w]
            current_len = word_len
        else:
            current_line.append(w)
            current_len += word_len
    if current_line:
        lines.append(current_line)
    return lines


def _ts(seconds: float) -> str:
    """Convert float seconds to ASS timestamp H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _burn_captions(input_path: Path, ass_path: Path, output_path: Path):
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
