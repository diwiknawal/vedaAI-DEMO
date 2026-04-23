"""
Pipeline Stage 6 — AI Scene Suggestions
Uses either Gemini or Local LLM (Ollama) to generate editorial suggestions for each clip.
"""
import json
import logging
import re
import httpx

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

            suggestions = None
            
            # --- Path A: Local LLM (Ollama) ---
            if settings.use_local_llm:
                try:
                    payload = {
                        "model": settings.llm_model,
                        "prompt": SUGGESTION_PROMPT.format(
                            platform=clip.platform,
                            duration=clip.duration_sec or 25.0,
                            score=clip.virality_score or 0,
                            transcript=transcript[:1000]
                        ),
                        "stream": False,
                        "format": "json"
                    }
                    resp = httpx.post(f"{settings.ollama_base_url}/api/generate", json=payload, timeout=60.0)
                    resp.raise_for_status()
                    raw_response = resp.json().get("response", "{}")
                    suggestions = _parse_json(raw_response)
                    logger.info(f"[ai_suggestions] clip {clip.id} suggested via Local LLM")
                except Exception as e:
                    logger.error(f"[ai_suggestions] Local LLM failed: {e}")
                    raise e

            # --- Path B: Gemini (Cloud API) ---
            elif settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = SUGGESTION_PROMPT.format(
                    platform=clip.platform,
                    duration=clip.duration_sec or 25.0,
                    score=clip.virality_score or 0,
                    transcript=transcript[:1000]
                )
                response = model.generate_content(prompt)
                suggestions = _parse_json(response.text)
                logger.info(f"[ai_suggestions] clip {clip.id} suggested via Gemini")

            else:
                raise ValueError("No valid AI provider configured")

            if suggestions:
                clip.ai_suggestions = suggestions
                db.commit()

        except Exception as e:
            logger.warning(f"[ai_suggestions] clip {clip.id} AI failed ({e}), falling back to heuristic")
            fallback = {
                "hook_text": "Wait for the end... 🔥",
                "suggested_title": f"Viral {clip.platform.title()} Clip",
                "text_overlays": [{"time": 0, "text": "Watch this!", "style": "title"}],
                "broll_prompts": ["Cinematic establishing shot"],
                "transition": "zoom_in",
                "music_mood": "energetic",
                "cta": "Follow for more!"
            }
            clip.ai_suggestions = fallback
            db.commit()

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
            try: return json.loads(m.group())
            except: pass
    return {}
