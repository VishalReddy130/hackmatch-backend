from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import get_current_user
from app.models.team import create_team_document, serialize_team
from app.schemas.team import (
    CreateTeamRequest,
    TeamListItem,
    TeamMemberInfo,
    TeamResponse,
    TeamWithMembersResponse,
)

router = APIRouter()


def _to_oid(id_str: str) -> ObjectId:
    """Parse a string into an ObjectId, raising 400 on bad format."""
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{id_str}' is not a valid ID",
        )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[TeamListItem],
    summary="Browse all teams",
)
async def list_teams(db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Public — no authentication required.
    Returns up to 100 teams sorted newest-first.
    Uses the compact TeamListItem shape (no full members array).
    """
    teams = await db["teams"].find().sort("created_at", -1).to_list(100)
    result = []
    for t in teams:
        s = serialize_team(t)
        result.append(
            TeamListItem(
                id=s["id"],
                name=s["name"],
                description=s["description"],
                member_count=s["member_count"],
                max_members=s["max_members"],
                is_full=s["member_count"] >= s["max_members"],
            )
        )
    return result


# ── Create ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new team",
)
async def create_team(
    body: CreateTeamRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Protected. The creator is automatically added as the first member
    and their user document is updated with the new team_id.

    A user can only be on one team at a time.
    """
    if current_user.get("team_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already on a team. Leave it before creating a new one.",
        )

    if await db["teams"].find_one({"name": body.name}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A team with this name already exists",
        )

    doc = create_team_document(
        name=body.name,
        description=body.description,
        created_by=current_user["_id"],
    )
    result = await db["teams"].insert_one(doc)
    team_id = result.inserted_id

    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"team_id": team_id}},
    )

    team = await db["teams"].find_one({"_id": team_id})
    return TeamResponse(**serialize_team(team))


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get(
    "/{team_id}",
    response_model=TeamWithMembersResponse,
    summary="Get team details with populated member info",
)
async def get_team(
    team_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Public. Fetches all members in a single $in query so the frontend
    gets name and AI role for each member without extra round-trips.
    """
    oid = _to_oid(team_id)

    team = await db["teams"].find_one({"_id": oid})
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    member_oids = team.get("members", [])
    members_info: list[TeamMemberInfo] = []

    async for member in db["users"].find({"_id": {"$in": member_oids}}):
        members_info.append(
            TeamMemberInfo(
                id=str(member["_id"]),
                username=member["username"],
                name=member.get("profile", {}).get("name", ""),
                primary_role=(
                    member["ai_analysis"].get("primary_role")
                    if member.get("ai_analysis")
                    else None
                ),
            )
        )

    serialized = serialize_team(team)
    return TeamWithMembersResponse(**serialized, members_info=members_info)


# ── Join ──────────────────────────────────────────────────────────────────────

@router.post(
    "/{team_id}/join",
    response_model=TeamResponse,
    summary="Join a team",
)
async def join_team(
    team_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Protected. Adds the user to the team and updates their team_id.

    Checks in order:
      1. User is not already on any team
      2. Team exists
      3. Team is not full (< max_members)
      4. User is not already in this specific team
    """
    if current_user.get("team_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already on a team. Leave it first.",
        )

    oid = _to_oid(team_id)
    team = await db["teams"].find_one({"_id": oid})
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if len(team["members"]) >= team["max_members"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This team is full",
        )

    if current_user["_id"] in team["members"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this team",
        )

    await db["teams"].update_one(
        {"_id": oid},
        {"$push": {"members": current_user["_id"]}},
    )
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"team_id": oid}},
    )

    updated = await db["teams"].find_one({"_id": oid})
    return TeamResponse(**serialize_team(updated))


# ── Leave ─────────────────────────────────────────────────────────────────────

@router.delete(
    "/{team_id}/leave",
    summary="Leave a team",
)
async def leave_team(
    team_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Protected. Removes the user from the team.

    Edge cases:
      - Last member leaves  → team document is deleted automatically
      - Creator leaves (team still has members) → ownership transfers to
        the next member in the list
    """
    oid = _to_oid(team_id)
    team = await db["teams"].find_one({"_id": oid})
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if current_user["_id"] not in team["members"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a member of this team",
        )

    # Remove user from team and clear their team_id reference
    await db["teams"].update_one(
        {"_id": oid},
        {"$pull": {"members": current_user["_id"]}},
    )
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"team_id": None}},
    )

    updated = await db["teams"].find_one({"_id": oid})

    # Team is now empty — clean it up
    if not updated["members"]:
        await db["teams"].delete_one({"_id": oid})
        return {"message": "You left the team. It was deleted as you were the last member."}

    # Creator left but team survives — transfer ownership
    if team["created_by"] == current_user["_id"]:
        await db["teams"].update_one(
            {"_id": oid},
            {"$set": {"created_by": updated["members"][0]}},
        )

    return {"message": "You have successfully left the team"}
