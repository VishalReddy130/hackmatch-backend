from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import get_current_user
from app.services.resume_service import parse_resume

router = APIRouter()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/upload", summary="Upload a PDF résumé and extract data from it")
async def upload_resume(
    file: UploadFile = File(..., description="PDF résumé, max 5 MB"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Upload a PDF résumé.  The server will:
      1. Validate the file type and size
      2. Extract raw text with pdfplumber
      3. Keyword-scan for ~120 known technologies → extracted_skills
      4. Attempt project-section parsing → projects list
      5. Store the result in the user's 'resume' sub-document in MongoDB
      6. Return a summary (raw_text is stored but never returned to the client)

    Re-uploading replaces any previously stored résumé.
    Phase 6 (AI analysis) will use the stored raw_text for a Gemini call.
    """
    # ── File-type check ──────────────────────────────────────────────────────
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted (.pdf extension required)",
        )

    # ── Read + size check ────────────────────────────────────────────────────
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the 5 MB limit "
                   f"({len(content) // 1024} KB received)",
        )

    # ── Parse ────────────────────────────────────────────────────────────────
    try:
        resume_data = parse_resume(content)
    except ValueError as exc:
        # No extractable text — probably a scanned image PDF
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Could not parse this PDF. "
                "Make sure it is a digital (text-based) PDF, not encrypted or corrupted."
            ),
        )

    # ── Persist ──────────────────────────────────────────────────────────────
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"resume": resume_data}},
    )

    # Return summary — raw_text stays server-side for the Gemini call
    return {
        "message": "Resume uploaded and parsed successfully",
        "extracted_skills": resume_data["extracted_skills"],
        "projects":         resume_data["projects"],
        "technologies":     resume_data["technologies"],
        "skills_count":     len(resume_data["extracted_skills"]),
        "projects_count":   len(resume_data["projects"]),
    }
