from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGODB_URL: str

    # ── JWT ───────────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── Gemini AI ─────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "HackMatch"
    DEBUG: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # silently ignore unknown env vars
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Import this singleton everywhere:
#   from app.config import settings
settings = get_settings()
