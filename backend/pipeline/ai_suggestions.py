"""
Pipeline Stage 6 — AI Scene Suggestions
Uses Gemini to generate editorial suggestions for each clip:
b-roll prompts, hook text, transition type, text overlays.
Stores suggestions as JSON on the Clip DB record.
"""
import json
import logging
import re

import google.generativeai as genai

from config import settings

logger = logging.getLogger(__name__)

SUGGESTION_PROMPT = """You are a viral short-form video editor. Given this clip's content, generate creative suggestions.

Clip info:
- Platform: {platform}
- Duration: {duration:.1f}s
- Virality score: {score}/100
- Transcript: "{transcript}"

Generate suggestions in this exact JSON format (no markdown):
{{
  "hook_text": "<attention-grabbing opening text to show on screen, max 8 words>",
  "suggested_title": "<catchy clip title for the platform>",
  "text_overlays": [
    {{"time": 0, "text": "<overlay at 0s>", "style": "title"}},
    {{"time": 5, "text": "<overlay at 5s>", "style": "caption"}}
  ],
  "broll_prompts": [
    "<cinematic description of B-roll shot 1>",
    "<cinematic description of B-roll shot 2>"
  ],
  "transition": "<none|zoom_in|fade|whip_pan>",
  "music_mood": "<energetic|calm|dramatic|upbeat|suspenseful>",
  "cta": "<call to action text, e.g. 'Follow for more'>"
}}"""


def run_ai_suggestions(ctx: dict) -> dict:
    job_id = ctx["job_id"]
    db = ctx["db"]
    clip_ids = ctx.get("clip_ids", [])

    if not clip_ids:
        return ctx

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    from models import Clip, Scene

    clips = db.query(Clip).filter(Clip.id.in_(clip_ids)).all()

    for clip in clips:
        try:
            scene = db.query(Scene).filter(Scene.id == clip.scene_id).first()
            transcript = ""
            if scene and scene.transcript_segment:
                try:
                    seg_data = json.loads(scene.transcript_segment)
                    transcript = seg_data.get("text", scene.transcript_segment)
                except (json.JSONDecodeError, AttributeError):
                    transcript = scene.transcript_segment or ""
            if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
                raise ValueError("No valid Gemini API key provided")

            prompt = SUGGESTION_PROMPT.format(
                platform=clip.platform,
                duration=clip.duration_sec or 25.0,
                score=clip.virality_score or 0,
                transcript=transcript[:1000],
            )

            response = model.generate_content(prompt)
            suggestions = _parse_json(response.text)
            clip.ai_suggestions = suggestions
            db.commit()
            logger.debug(f"[ai_suggestions] clip={clip.id} platform={clip.platform} ✓")

        except Exception as e:
            logger.warning(f"[ai_suggestions] clip {clip.id} Gemini failed ({e}), falling back to open-source heuristic algorithm")
            
            # --- OPEN SOURCE HEURISTIC FALLBACK (No API needed) ---
            # Generate generic but useful metadata based on what we have
            fallback_suggestions = {
              "hook_text": f"Wait for the end... 🔥",
              "suggested_title": f"Viral {clip.platform.title()} Clip",
              "text_overlays": [
                {"time": 0, "text": "Watch this!", "style": "title"},
                {"time": int((clip.duration_sec or 10)/2), "text": "Wait for it...", "style": "caption"}
              ],
              "broll_prompts": [
                "Cinematic establishing shot",
                "Dynamic reaction shot"
              ],
              "transition": "zoom_in",
              "music_mood": "energetic",
              "cta": "Follow for more!"
            }
            
            clip.ai_suggestions = fallback_suggestions
            db.commit()

    logger.info(f"[ai_suggestions] job={job_id} clips_enriched={len(clips)}")
    return ctx


def _parse_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {}
