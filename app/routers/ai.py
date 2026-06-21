from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import get_current_user
from app.services.ai_service import analyze_profile_with_gemini

router = APIRouter()


@router.post("/analyze", summary="Generate an AI profile analysis with Gemini")
async def analyze_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Calls Gemini 1.5 Flash with the user's profile and résumé text,
    then stores the result in the 'ai_analysis' sub-document.

    Works even without a résumé — just has less context to work with.
    Re-running overwrites any previous analysis.

    Returns the generated analysis directly.
    """
    try:
        analysis = await analyze_profile_with_gemini(current_user)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    # Persist
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"ai_analysis": analysis}},
    )

    # Serialize datetime before returning
    response = {**analysis}
    if isinstance(response.get("generated_at"), datetime):
        response["generated_at"] = response["generated_at"].isoformat()

    return response
