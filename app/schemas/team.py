from pydantic import BaseModel, field_validator


# ── Requests ──────────────────────────────────────────────────────────────────

class CreateTeamRequest(BaseModel):
    """Body for POST /teams"""

    name: str
    description: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Team name cannot be empty")
        if len(v) > 60:
            raise ValueError("Team name must be 60 characters or fewer")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 300:
            raise ValueError("Description must be 300 characters or fewer")
        return v


# ── Responses ─────────────────────────────────────────────────────────────────

class TeamMemberInfo(BaseModel):
    """
    Compact member info embedded in TeamWithMembersResponse.
    Avoids a second round-trip to look up members on the frontend.
    """
    id: str
    username: str
    name: str                       # profile.name
    primary_role: str | None = None # ai_analysis.primary_role


class TeamResponse(BaseModel):
    """
    Standard team response for POST /teams and GET /teams/{id}.
    members is a list of user ID strings.
    """
    id: str
    name: str
    description: str
    created_by: str
    members: list[str]
    max_members: int
    created_at: str
    member_count: int = 0


class TeamWithMembersResponse(BaseModel):
    """
    Extended team detail for GET /teams/{id}.
    Includes populated member info so the frontend doesn't need
    a separate request per member.
    """
    id: str
    name: str
    description: str
    created_by: str
    members: list[str]
    max_members: int
    created_at: str
    member_count: int = 0
    members_info: list[TeamMemberInfo] = []


class TeamListItem(BaseModel):
    """
    Compact team entry for GET /teams (the browse list).
    Omits the full members array to keep the response small.
    """
    id: str
    name: str
    description: str
    member_count: int
    max_members: int
    is_full: bool = False
