from pydantic import BaseModel, field_validator


# ── Nested sub-schemas (reused in multiple responses) ─────────────────────────

class ProjectSchema(BaseModel):
    """One project entry extracted from the resume."""
    name: str
    description: str = ""
    technologies: list[str] = []


class ResumeDataSchema(BaseModel):
    """Resume data stored after PDF upload + extraction (Phase 5)."""
    extracted_skills: list[str] = []
    projects: list[ProjectSchema] = []
    technologies: list[str] = []
    uploaded_at: str | None = None


class AIAnalysisSchema(BaseModel):
    """AI-generated profile analysis from Gemini (Phase 6)."""
    primary_role: str = ""
    skill_summary: str = ""
    strengths: list[str] = []
    areas_to_improve: list[str] = []
    generated_at: str | None = None


class UserProfileSchema(BaseModel):
    """
    The 'profile' sub-document inside a user.
    Mirrors the nested dict stored in MongoDB.
    """
    name: str = ""
    college: str = ""
    branch: str = ""
    year: int | None = None
    skills: list[str] = []
    interests: list[str] = []
    github_url: str = ""
    linkedin_url: str = ""


# ── Requests ──────────────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    """
    Body for PUT /users/me

    Every field is optional — clients send only what changed.
    The router converts non-None fields into a MongoDB $set patch.

    Example: { "skills": ["Python", "React"], "college": "MIT" }
    → only updates those two fields, leaves everything else intact.
    """
    name: str | None = None
    college: str | None = None
    branch: str | None = None
    year: int | None = None
    skills: list[str] | None = None
    interests: list[str] | None = None
    github_url: str | None = None
    linkedin_url: str | None = None

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int | None) -> int | None:
        if v is not None and v not in (1, 2, 3, 4):
            raise ValueError("Year must be 1, 2, 3, or 4")
        return v

    @field_validator("skills", "interests")
    @classmethod
    def clean_list(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        # Strip whitespace, deduplicate, drop empty strings
        seen: set[str] = set()
        result: list[str] = []
        for item in v:
            clean = item.strip()
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result


# ── Responses ─────────────────────────────────────────────────────────────────

class UserMeResponse(BaseModel):
    """
    Full profile returned at GET /users/me (authenticated).
    Includes private fields (email) and the computed profile_completion score.
    """
    id: str
    username: str
    email: str
    created_at: str
    profile: UserProfileSchema
    resume: ResumeDataSchema | None = None
    ai_analysis: AIAnalysisSchema | None = None
    team_id: str | None = None
    profile_completion: int = 0  # 0-100, computed by calculate_profile_completion()


class PublicUserResponse(BaseModel):
    """
    Public profile returned at GET /users/{username}.
    Email, password_hash, and other private fields are excluded.
    """
    id: str
    username: str
    profile: UserProfileSchema
    resume: ResumeDataSchema | None = None
    ai_analysis: AIAnalysisSchema | None = None
    team_id: str | None = None


class MatchedUserResponse(BaseModel):
    """
    A potential teammate returned in GET /matches (Phase 7).
    Extends the public profile with a compatibility score and reason.
    """
    id: str
    username: str
    profile: UserProfileSchema
    ai_analysis: AIAnalysisSchema | None = None
    team_id: str | None = None
    compatibility_score: int = 0    # 0-100
    match_reason: str = ""          # human-readable explanation
