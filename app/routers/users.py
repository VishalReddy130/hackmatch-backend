from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import get_current_user
from app.models.user import calculate_profile_completion, serialize_user
from app.schemas.user import PublicUserResponse, UpdateProfileRequest, UserMeResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get the current user's full profile",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Protected — requires a valid JWT.

    Returns the full profile including:
      - private fields (email)
      - computed profile_completion score (0-100)
      - resume data if uploaded
      - ai_analysis if generated
    """
    serialized = serialize_user(current_user)
    serialized["profile_completion"] = calculate_profile_completion(current_user)
    return UserMeResponse(**serialized)


@router.put(
    "/me",
    response_model=UserMeResponse,
    summary="Update the current user's profile",
)
async def update_me(
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Partial update — only send the fields you want to change.

    Uses MongoDB dot-notation $set so unmentioned profile fields are untouched:
      { "skills": ["Python"], "college": "MIT" }
      → sets profile.skills and profile.college only

    If the request body is empty, returns the current profile unchanged.
    """
    patch = body.model_dump(exclude_none=True)

    if patch:
        set_doc = {f"profile.{key}": val for key, val in patch.items()}
        await db["users"].update_one(
            {"_id": current_user["_id"]},
            {"$set": set_doc},
        )

    # Always re-fetch to return the actual database state
    updated = await db["users"].find_one({"_id": current_user["_id"]})
    serialized = serialize_user(updated)
    serialized["profile_completion"] = calculate_profile_completion(updated)
    return UserMeResponse(**serialized)


@router.get(
    "/{username}",
    response_model=PublicUserResponse,
    summary="Get a user's public profile",
)
async def get_public_profile(
    username: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Public — no authentication required.
    Accessible at /profile/{username} on the frontend.

    Returns skills, projects, AI summary, and team status.
    Omits email and all private fields.
    """
    user = await db["users"].find_one({"username": username.lower()})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user found with username '{username}'",
        )
    return PublicUserResponse(**serialize_user(user))
