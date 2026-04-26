"""
CV routes — AI-powered CV generation and download.
"""
from uuid import UUID
from typing import Optional
import json
import io

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.models.application import GeneratedCV
from app.services.cv_service import (
    generate_and_save_cv,
    get_my_generated_cvs,
)

router = APIRouter()


class CVGenerateRequest(BaseModel):
    job_id: UUID
    file_format: str = "pdf"
    additional_answers: Optional[dict] = None


class CVAnswersRequest(BaseModel):
    job_id: UUID
    file_format: str = "pdf"
    answers: dict


@router.post(
    "/generate",
    summary="Generate an AI-tailored CV for a specific job",
)
async def generate_cv(
    data: CVGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a professional, AI-tailored CV for a specific job.

    The AI will:
    - Analyze the job requirements
    - Select your most relevant skills
    - Write a tailored professional summary
    - Format everything professionally

    If your profile is missing important information, the response will
    include **missing_info_questions** — answer these and call
    `POST /cv/generate-with-answers` for a better CV.

    Supports **pdf** and **docx** formats.
    """
    generated_cv = await generate_and_save_cv(
        db=db,
        user=current_user,
        job_id=data.job_id,
        file_format=data.file_format,
        additional_answers=data.additional_answers,
    )

    missing_questions = getattr(generated_cv, "_missing_questions", [])

    return {
        "cv_id": str(generated_cv.id),
        "file_name": generated_cv.file_name,
        "file_format": generated_cv.file_format,
        "storage_url": generated_cv.storage_url,
        "generated_at": str(generated_cv.generated_at),
        "missing_info_questions": missing_questions,
        "message": (
            "CV generated successfully! Download it using GET /cv/{cv_id}/download"
            if not missing_questions
            else "CV generated but we have some questions to improve it. "
                 "Answer them and call POST /cv/generate-with-answers for a better CV."
        ),
    }


@router.post(
    "/generate-with-answers",
    summary="Regenerate CV after answering clarifying questions",
)
async def generate_cv_with_answers(
    data: CVAnswersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Regenerate your CV after answering the AI's clarifying questions.
    Provide your answers in the `answers` dict.

    Example answers:
```json
    {
        "experience": "I worked as an intern at XYZ for 6 months doing Python development",
        "projects": "I built a e-commerce app using React and Node.js",
        "certifications": "AWS Cloud Practitioner, Google Analytics",
        "skills": "I also know Docker and Kubernetes"
    }
```
    """
    generated_cv = await generate_and_save_cv(
        db=db,
        user=current_user,
        job_id=data.job_id,
        file_format=data.file_format,
        additional_answers=data.answers,
    )

    return {
        "cv_id": str(generated_cv.id),
        "file_name": generated_cv.file_name,
        "file_format": generated_cv.file_format,
        "storage_url": generated_cv.storage_url,
        "generated_at": str(generated_cv.generated_at),
        "message": "CV regenerated with your additional information!",
    }


@router.get(
    "/{cv_id}/download",
    summary="Download a generated CV",
)
async def download_cv(
    cv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download a previously generated CV as a file.
    Regenerates the file from saved content snapshot.
    """
    stmt = select(GeneratedCV).where(
        GeneratedCV.id == cv_id,
        GeneratedCV.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    generated_cv = result.scalar_one_or_none()

    if not generated_cv:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found.",
        )

    # Regenerate file from saved content snapshot
    cv_data = json.loads(generated_cv.content_snapshot)

    from app.tools.cv_formatter import generate_cv_pdf, generate_cv_docx

    if generated_cv.file_format == "pdf":
        file_bytes = generate_cv_pdf(cv_data)
        media_type = "application/pdf"
    else:
        file_bytes = generate_cv_docx(cv_data)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={generated_cv.file_name}",
            "Content-Length": str(len(file_bytes)),
        },
    )


@router.get(
    "/",
    summary="Get all my generated CVs",
)
async def list_my_cvs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a list of all CVs you have generated."""
    cvs = await get_my_generated_cvs(db, current_user)
    return {
        "cvs": [
            {
                "id": str(cv.id),
                "job_title": cv.job.title if cv.job else "Unknown",
                "file_name": cv.file_name,
                "file_format": cv.file_format,
                "storage_url": cv.storage_url,
                "generated_at": str(cv.generated_at),
            }
            for cv in cvs
        ],
        "total": len(cvs),
    }