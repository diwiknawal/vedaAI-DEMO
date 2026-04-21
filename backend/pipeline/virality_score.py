"""
Pipeline Stage 4 — Virality Score
Uses Gemini Flash to score each scene's viral potential (0-100).
Selects top scenes above the virality threshold for clipping.
"""
import json
import logging
import re

import google.generativeai as genai

from config import settings

logger = logging.getLogger(__name__)

SCORE_PROMPT = """You are a viral social media content expert. Analyze this video segment and score its viral potential for TikTok/Reels/Shorts on a scale of 0-100.

Segment details:
- Duration: {duration:.1f} seconds
- Transcript: "{transcript}"

Score based on:
1. Hook power — does it grab attention in first 3 seconds? (25pts)
2. Emotional resonance — humor, shock, inspiration, relatability (25pts)
3. Quotability — punchy, memorable, shareable lines (20pts)
4. Pacing — fast enough for short-form consumption (15pts)
5. Standalone clarity — makes sense without context (15pts)

Return ONLY valid JSON, no markdown:
{{
  "score": <integer 0-100>,
  "hook": "<one sentence describing the hook>",
  "reasoning": "<2-3 sentence explanation>",
  "suggested_title": "<catchy title for this clip>"
}}"""


def run_virality_score(ctx: dict) -> dict:
    job_id = ctx["job_id"]
    db = ctx["db"]
    scene_ids = ctx.get("scene_ids", [])

    from models import Scene
    scenes = db.query(Scene).filter(Scene.id.in_(scene_ids)).all()

    if not scenes:
        logger.warning(f"[virality] job={job_id} no scenes to score")
        return {**ctx, "selected_scene_ids": []}

    # ── Configure Gemini ──────────────────────────────────────────────
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    scored = []
    for scene in scenes:
        transcript = (scene.transcript_segment or "").strip()
        if not transcript:
            # No speech — heuristic score based on duration
            score = 40 if 20 <= scene.duration_sec <= 35 else 20
            scene.virality_score = score
            scene.motion_score = None
            db.commit()
            scored.append((scene, score))
            continue

        try:
            if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
                raise ValueError("No valid Gemini API key provided")

            prompt = SCORE_PROMPT.format(
                duration=scene.duration_sec,
                transcript=transcript[:1500],   # token budget
            )
            response = model.generate_content(prompt)
            result = _parse_json(response.text)
            score = max(0, min(100, int(result.get("score", 0))))

            scene.virality_score = score
            # Store hook + title in the scene for later use
            scene.transcript_segment = json.dumps({
                "text": transcript,
                "hook": result.get("hook", ""),
                "reasoning": result.get("reasoning", ""),
                "suggested_title": result.get("suggested_title", ""),
            })
            db.commit()
            scored.append((scene, score))
            logger.debug(f"  scene {scene.scene_index} score={score}")

        except Exception as e:
            logger.warning(f"[virality] scene {scene.id} Gemini failed ({e}), falling back to open-source heuristic algorithm")
            
            # --- OPEN SOURCE HEURISTIC FALLBACK (No API needed, 0MB RAM) ---
            score = 50 # Base score
            
            # 1. Duration check (sweet spot is 15-40 seconds)
            if 15 <= scene.duration_sec <= 40:
                score += 20
            elif scene.duration_sec > 60 or scene.duration_sec < 5:
                score -= 20
                
            # 2. Keyword density (buzzwords that indicate high engagement)
            viral_keywords = ["crazy", "wow", "wait", "look", "how to", "secret", "never", "always", "best", "worst", "omg", "hack", "trick"]
            lower_transcript = transcript.lower()
            keyword_hits = sum(1 for word in viral_keywords if word in lower_transcript)
            score += (keyword_hits * 5)
            
            score = max(0, min(100, score))
            
            scene.virality_score = score
            scene.transcript_segment = json.dumps({
                "text": transcript,
                "hook": f"Watch what happens in this {int(scene.duration_sec)}s clip!",
                "reasoning": "Selected using open-source heuristic transcript analysis.",
                "suggested_title": f"Viral Moment #{scene.scene_index + 1}",
            })
            db.commit()
            scored.append((scene, score))

    # ── Select top scenes above threshold ─────────────────────────────
    scored.sort(key=lambda x: x[1], reverse=True)
    selected = [
        s for s, score in scored
        if score >= settings.virality_threshold
    ][:5]   # max 5 clips per video

    for s in selected:
        s.selected_for_clip = True
    db.commit()

    logger.info(
        f"[virality] job={job_id} scored={len(scored)} "
        f"selected={len(selected)} threshold={settings.virality_threshold}"
    )
    return {**ctx, "selected_scene_ids": [s.id for s in selected]}


def _parse_json(text: str) -> dict:
    """Robustly extract JSON from LLM response (strips markdown fences if present)."""
    text = text.strip()
    # Strip ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort — find first { ... }
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    return {"score": 0}
