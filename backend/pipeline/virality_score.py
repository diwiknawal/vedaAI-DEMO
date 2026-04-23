"""
Pipeline Stage 4 — Virality Score
Uses either Gemini Flash or Local LLM (Ollama) to score each scene's viral potential (0-100).
Selects top scenes above the virality threshold for clipping.
"""
import json
import logging
import re
import httpx

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

    scored = []
    for scene in scenes:
        transcript = (scene.transcript_segment or "").strip()
        if not transcript:
            score = 40 if 20 <= scene.duration_sec <= 35 else 20
            scene.virality_score = score
            db.commit()
            scored.append((scene, score))
            continue

        try:
            result = None
            
            # --- Path A: Local LLM (Ollama) ---
            if settings.use_local_llm:
                try:
                    payload = {
                        "model": settings.llm_model,
                        "prompt": SCORE_PROMPT.format(duration=scene.duration_sec, transcript=transcript[:1500]),
                        "stream": False,
                        "format": "json"
                    }
                    resp = httpx.post(f"{settings.ollama_base_url}/api/generate", json=payload, timeout=60.0)
                    resp.raise_for_status()
                    raw_response = resp.json().get("response", "{}")
                    result = _parse_json(raw_response)
                    logger.info(f"[virality] scene {scene.scene_index} scored via Local LLM ({settings.llm_model})")
                except Exception as e:
                    logger.error(f"[virality] Local LLM failed: {e}")
                    raise e

            # --- Path B: Gemini (Cloud API) ---
            elif settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = SCORE_PROMPT.format(duration=scene.duration_sec, transcript=transcript[:1500])
                response = model.generate_content(prompt)
                result = _parse_json(response.text)
                logger.info(f"[virality] scene {scene.scene_index} scored via Gemini")
            
            else:
                raise ValueError("No valid AI provider configured (Gemini or Local LLM)")

            if result:
                score = max(0, min(100, int(result.get("score", 0))))
                scene.virality_score = score
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
            logger.warning(f"[virality] AI scoring failed ({e}), falling back to heuristic")
            
            # --- Path C: Heuristic Fallback (No AI) ---
            score = 50 
            if 15 <= scene.duration_sec <= 40: score += 20
            elif scene.duration_sec > 60 or scene.duration_sec < 5: score -= 20
            
            viral_keywords = ["crazy", "wow", "wait", "look", "secret", "never", "always", "best", "worst", "omg", "hack", "trick"]
            keyword_hits = sum(1 for word in viral_keywords if word in transcript.lower())
            score += (keyword_hits * 5)
            
            score = max(0, min(100, score))
            scene.virality_score = score
            scene.transcript_segment = json.dumps({
                "text": transcript,
                "hook": f"Watch what happens in this {int(scene.duration_sec)}s clip!",
                "reasoning": "Heuristic fallback analysis.",
                "suggested_title": f"Viral Moment #{scene.scene_index + 1}",
            })
            db.commit()
            scored.append((scene, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    selected = [s for s, score in scored if score >= settings.virality_threshold][:5]

    for s in selected:
        s.selected_for_clip = True
    db.commit()

    return {**ctx, "selected_scene_ids": [s.id for s in selected]}


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
    return {"score": 0}
