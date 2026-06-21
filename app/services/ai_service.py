"""
app/services/ai_service.py

Phase 6 — Gemini AI profile analysis.

Builds a structured prompt from the user's profile + résumé text,
calls the Gemini 1.5 Flash model, and parses the JSON response into
the ai_analysis sub-document structure stored in MongoDB.
"""

import asyncio
import json
import logging
from datetime import datetime

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

# Configure once — settings.GEMINI_API_KEY is validated at startup
genai.configure(api_key=settings.GEMINI_API_KEY)

_MODEL = "gemini-1.5-flash"   # Fast, generous free quota, good JSON reliability


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(user: dict) -> str:
    profile      = user.get("profile") or {}
    resume       = user.get("resume")  or {}

    skills        = profile.get("skills", [])
    resume_skills = resume.get("extracted_skills", [])
    all_skills    = sorted(set(skills + resume_skills))
    projects      = resume.get("projects", [])
    raw_text      = resume.get("raw_text", "")

    project_names = ", ".join(p["name"] for p in projects) if projects else "None listed"

    return f"""You are a technical career advisor analyzing a student's hackathon profile.

Profile data:
- Major / Branch : {profile.get("branch") or "Not specified"}
- Year of study  : {profile.get("year")   or "Not specified"}
- Self-reported skills : {", ".join(skills)        or "None listed"}
- Resume skills        : {", ".join(resume_skills) or "None extracted"}
- All skills combined  : {", ".join(all_skills)    or "None"}
- Projects listed      : {project_names}
- Résumé text excerpt  :
{raw_text[:2500] or "No résumé uploaded yet"}

Respond ONLY with a valid JSON object. No markdown, no code fences, no explanation.
Use this exact schema:
{{
  "primary_role":      "<one of: Frontend Developer | Backend Developer | Full-Stack Developer | ML Engineer | Data Scientist | DevOps Engineer | Mobile Developer | UI/UX Designer | Blockchain Developer | Other>",
  "skill_summary":     "<2–3 sentences summarising the student's technical profile and focus area>",
  "strengths":         ["<specific strength 1>", "<specific strength 2>", "<specific strength 3>"],
  "areas_to_improve":  ["<specific area 1>",     "<specific area 2>",     "<specific area 3>"]
}}"""


# ── Synchronous Gemini call (runs in a thread executor) ───────────────────────

def _call_gemini_sync(user: dict) -> dict:
    prompt   = _build_prompt(user)
    model    = genai.GenerativeModel(_MODEL)
    response = model.generate_content(prompt)
    raw      = response.text.strip()

    # Strip markdown code fences if the model wrapped its output
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw   = "\n".join(lines[1:-1]).strip()

    result = json.loads(raw)
    result["generated_at"] = datetime.utcnow()
    return result


# ── Public async interface ────────────────────────────────────────────────────

async def analyze_profile_with_gemini(user: dict) -> dict:
    """
    Generate an AI profile analysis for the given user document.

    Runs the blocking Gemini HTTP call in a thread executor so it does
    not stall the FastAPI async event loop.

    Returns a dict matching the 'ai_analysis' MongoDB sub-document.
    Raises RuntimeError with a user-friendly message on any failure.
    """
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _call_gemini_sync, user)
    except json.JSONDecodeError:
        logger.error("Gemini returned non-JSON response")
        raise RuntimeError(
            "AI model returned an unexpected format. Please try again in a moment."
        )
    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        raise RuntimeError(
            f"AI analysis failed: {exc}. "
            "Verify your GEMINI_API_KEY and that your account has available quota."
        )
