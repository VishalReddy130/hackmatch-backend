from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────
# CryptContext manages bcrypt rounds automatically.
# deprecated="auto" means old/weak hashes are silently re-hashed on next login.

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt. Store the result — never the original."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Compare plain text against a bcrypt hash.
    Runs in constant time to prevent timing-attack enumeration.
    """
    return pwd_context.verify(plain, hashed)


# ── JWT tokens ────────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    """
    Issue a signed JWT for the given MongoDB user _id.

    Payload:
        sub — user _id as a string (retrieved in get_current_user)
        exp — UTC expiry set by ACCESS_TOKEN_EXPIRE_MINUTES in .env
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> dict | None:
    """
    Decode and validate a JWT.
    Returns the payload dict on success, None if invalid or expired.
    Called by get_current_user() in dependencies.py on every protected request.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        return None
