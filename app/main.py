from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routers import auth, users, resume, ai, matches, teams


# ── Lifespan ──────────────────────────────────────────────────────────────────
# Replaces the deprecated @app.on_event("startup") / @app.on_event("shutdown").
# Everything before `yield` runs on startup; after `yield` runs on shutdown.

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="HackMatch API — Connect with hackathon teammates",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# Allows the Next.js frontend to call this API from the browser.
#   Development:  FRONTEND_URL=http://localhost:3000
#   Production:   FRONTEND_URL=https://your-app.vercel.app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,    prefix="/auth",    tags=["auth"])
app.include_router(users.router,   prefix="/users",   tags=["users"])
app.include_router(resume.router,  prefix="/resume",  tags=["resume"])
app.include_router(ai.router,      prefix="/ai",      tags=["ai"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(teams.router,   prefix="/teams",   tags=["teams"])


# ── Utility endpoints ─────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    """
    Render pings this every 30 s to verify the service is alive.
    Also used after deployment to confirm the server started correctly.
    """
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/", tags=["root"])
async def root():
    return {
        "app": settings.APP_NAME,
        "message": "API is running",
        "docs": "/docs",
    }
