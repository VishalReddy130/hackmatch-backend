from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import get_current_user
from app.models.user import serialize_user
from app.schemas.user import MatchedUserResponse
from app.services.matching_service import compute_match_score

router = APIRouter()


@router.get(
    "",
    response_model=list[MatchedUserResponse],
    summary="Get potential teammates ranked by compatibility score",
)
async def get_matches(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Returns all other users scored against the current user, sorted
    highest-compatibility-first.

    Scoring (0-100):
      50 pts — complementary skills (what they have that you don't)
      30 pts — shared interests     (Jaccard overlap)
      20 pts — same graduation year (binary)

    Capped at the top 50 results for performance.
    Users with a score of 0 are still included — they may still be useful
    if the current user hasn't filled their profile yet.
    """
    # Fetch everyone except the current user (up to 500 for scoring)
    cursor = db["users"].find({"_id": {"$ne": current_user["_id"]}})
    all_users = await cursor.to_list(500)

    matches: list[MatchedUserResponse] = []

    for user in all_users:
        score, reason = compute_match_score(current_user, user)
        serialized = serialize_user(user)
        matches.append(
            MatchedUserResponse(
                **serialized,
                compatibility_score=score,
                match_reason=reason,
            )
        )

    matches.sort(key=lambda m: m.compatibility_score, reverse=True)
    return matches[:50]
