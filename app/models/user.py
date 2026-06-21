"""
app/models/user.py

Utilities for the 'users' MongoDB collection.

MongoDB document structure:
{
    "_id": ObjectId,
    "username": str,          # unique, lowercase, 3-30 chars
    "email": str,             # unique, lowercase
    "password_hash": str,     # bcrypt hash — NEVER returned in responses
    "created_at": datetime,
    "profile": {
        "name": str,
        "college": str,
        "branch": str,        # e.g. "Computer Science"
        "year": int | None,   # 1-4
        "skills": [str],      # e.g. ["Python", "React", "SQL"]
        "interests": [str],   # e.g. ["AI", "Web Dev", "Hackathons"]
        "github_url": str,
        "linkedin_url": str
    },
    "resume": {               # None until the user uploads a PDF
        "extracted_skills": [str],
        "projects": [
            {
                "name": str,
                "description": str,
                "technologies": [str]
            }
        ],
        "technologies": [str],
        "uploaded_at": datetime
    },
    "ai_analysis": {          # None until the user runs AI analysis
        "primary_role": str,          # e.g. "Backend Developer"
        "skill_summary": str,
        "strengths": [str],
        "areas_to_improve": [str],
        "generated_at": datetime
    },
    "team_id": ObjectId | None    # None if not on a team
}
"""

from datetime import datetime


def create_user_document(
    username: str,
    email: str,
    password_hash: str,
) -> dict:
    """
    Build a new user dict ready for db["users"].insert_one().
    MongoDB auto-generates _id on insert.

    Profile fields start empty — the user fills them on their dashboard.
    resume and ai_analysis start as None — set in Phase 5 and Phase 6.
    """
    return {
        "username": username.lower().strip(),
        "email": email.lower().strip(),
        "password_hash": password_hash,
        "created_at": datetime.utcnow(),
        "profile": {
            "name": "",
            "college": "",
            "branch": "",
            "year": None,
            "skills": [],
            "interests": [],
            "github_url": "",
            "linkedin_url": "",
        },
        "resume": None,
        "ai_analysis": None,
        "team_id": None,
    }


def serialize_user(user: dict | None) -> dict | None:
    """
    Convert a raw MongoDB user document into a JSON-safe dict.

    What this does:
      - Renames _id → id and converts ObjectId → str
      - Converts team_id ObjectId → str
      - Converts all datetime fields → ISO 8601 strings
      - Removes password_hash (NEVER expose it in API responses)
    """
    if user is None:
        return None

    result = {**user}

    # _id  →  id  (string)
    result["id"] = str(result.pop("_id"))

    # team_id ObjectId → string
    if result.get("team_id") is not None:
        result["team_id"] = str(result["team_id"])

    # Top-level datetime
    if isinstance(result.get("created_at"), datetime):
        result["created_at"] = result["created_at"].isoformat()

    # Nested datetimes inside resume
    if result.get("resume"):
        resume = result["resume"]
        if isinstance(resume.get("uploaded_at"), datetime):
            resume["uploaded_at"] = resume["uploaded_at"].isoformat()

    # Nested datetimes inside ai_analysis
    if result.get("ai_analysis"):
        analysis = result["ai_analysis"]
        if isinstance(analysis.get("generated_at"), datetime):
            analysis["generated_at"] = analysis["generated_at"].isoformat()

    # Security: strip the password hash
    result.pop("password_hash", None)

    return result


def calculate_profile_completion(user: dict) -> int:
    """
    Return a 0–100 completion percentage.

    10 equally-weighted checks:
      1.  profile.name
      2.  profile.college
      3.  profile.branch
      4.  profile.year
      5.  profile.skills (non-empty list)
      6.  profile.interests (non-empty list)
      7.  profile.github_url
      8.  profile.linkedin_url
      9.  resume uploaded
      10. ai_analysis generated
    """
    profile = user.get("profile", {})

    checks = [
        bool(profile.get("name")),
        bool(profile.get("college")),
        bool(profile.get("branch")),
        bool(profile.get("year")),
        bool(profile.get("skills")),
        bool(profile.get("interests")),
        bool(profile.get("github_url")),
        bool(profile.get("linkedin_url")),
        bool(user.get("resume")),
        bool(user.get("ai_analysis")),
    ]

    return int(sum(checks) / len(checks) * 100)
