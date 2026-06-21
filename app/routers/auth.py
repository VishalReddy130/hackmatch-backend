from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.models.user import create_user_document
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
async def register(
    body: RegisterRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Register a new user.

    - Username/password are validated by RegisterRequest (schema)
    - Email and username must be unique (enforced by DB index + check here)
    - Password is bcrypt-hashed before storage — plain text is never persisted
    - Returns a JWT immediately so the client is logged in right after signup
    """
    # ── Uniqueness checks ────────────────────────────────────────────────────
    if await db["users"].find_one({"email": body.email.lower()}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    if await db["users"].find_one({"username": body.username}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken",
        )

    # ── Persist ──────────────────────────────────────────────────────────────
    doc = create_user_document(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    result = await db["users"].insert_one(doc)

    return TokenResponse(
        access_token=create_access_token(str(result.inserted_id)),
        username=body.username,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT",
)
async def login(
    body: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Authenticate with email + password.

    The error message is intentionally vague ("Invalid email or password")
    for both wrong-email and wrong-password cases to prevent account
    enumeration attacks.
    """
    user = await db["users"].find_one({"email": body.email.lower()})

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return TokenResponse(
        access_token=create_access_token(str(user["_id"])),
        username=user["username"],
    )
