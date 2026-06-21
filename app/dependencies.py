from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.database import get_database
from app.services.auth_service import verify_token

# Reads the "Authorization: Bearer <token>" header automatically
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """
    Reusable FastAPI dependency for any protected route.

    Flow:
      1. Extracts Bearer token from Authorization header
      2. Decodes + validates the JWT signature and expiry
      3. Looks up the user in MongoDB by the 'sub' claim (user _id)
      4. Returns the full user document as a dict

    Raises 401 if the token is missing, invalid, or expired.
    Raises 404 if the user no longer exists in the database.

    Usage in any router:
        from app.dependencies import get_current_user

        @router.get("/me")
        async def get_me(current_user: dict = Depends(get_current_user)):
            return current_user
    """
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing subject claim",
        )

    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
        )

    user = await db["users"].find_one({"_id": object_id})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User no longer exists",
        )

    return user
