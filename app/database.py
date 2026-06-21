import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    """Holds the single Motor client instance for the lifetime of the app."""
    client: AsyncIOMotorClient | None = None


mongodb = MongoDB()


async def ensure_indexes(db) -> None:
    """
    Create MongoDB indexes for the users and teams collections.

    Safe to call on every startup — MongoDB is idempotent about index
    creation and skips indexes that already exist.

    Indexes:
      users.email    — unique  (login lookups)
      users.username — unique  (public profile URLs)
      teams.name     — sorted  (team browse list)
    """
    await db["users"].create_index("email",    unique=True)
    await db["users"].create_index("username", unique=True)
    await db["teams"].create_index("name")
    logger.info("✓ Indexes ensured")


async def connect_to_mongo() -> None:
    """
    Open the connection to MongoDB Atlas.
    Called once at application startup (via FastAPI lifespan).

    Motor is lazy — it won't actually connect until the first operation,
    but we ping immediately so startup fails fast on bad credentials.
    """
    logger.info("Connecting to MongoDB Atlas...")
    mongodb.client = AsyncIOMotorClient(settings.MONGODB_URL)

    # Confirm connection before accepting traffic
    await mongodb.client.admin.command("ping")

    # Create indexes (idempotent — safe to run on every boot)
    await ensure_indexes(mongodb.client.hackmatch)
    logger.info("✓ MongoDB ready")


async def close_mongo_connection() -> None:
    """
    Close the connection gracefully on app shutdown.
    Called once at application shutdown (via FastAPI lifespan).
    """
    if mongodb.client:
        mongodb.client.close()
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """
    FastAPI dependency that returns the 'hackmatch' database object.

    MongoDB Atlas creates the database lazily on first write —
    you don't need to create it manually in the Atlas UI.

    Usage in any router:
        @router.get("/example")
        async def example(db: AsyncIOMotorDatabase = Depends(get_database)):
            result = await db["users"].find_one({"email": "test@example.com"})
    """
    return mongodb.client.hackmatch
