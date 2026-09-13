"""Global-admin localization review, queue, backfill, and diagnostics endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.core.config import settings
from app.db.database import get_db
from app.knowledge.models import KnowledgeLocalization, LocalizationJob
from app.localization.backfill import LocalizationBackfillService
from app.localization.queue import LocalizationQueueService
from app.localization.schemas import (
    LocalizationBackfillRequest,
    LocalizationBackfillResponse,
    LocalizationJobPage,
    LocalizationJobRequest,
    LocalizationJobResponse,
    LocalizationPage,
    LocalizationResponse,
    LocalizationReviewRequest,
)
from app.localization.service import ContentLocalizationService
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit


router = APIRouter()


def _localization_or_404(db: Session, localization_id: UUID) -> KnowledgeLocalization:
    row = db.get(KnowledgeLocalization, localization_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "localization_not_found"})
    return row


def _job_or_404(db: Session, job_id: int) -> LocalizationJob:
    row = db.get(LocalizationJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "localization_job_not_found"})
    return row


def _audit(
    db: Session,
    admin: User,
    *,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict | None = None,
) -> None:
    db.add(
        WorkspaceAudit(
            actor_id=admin.id,
            workspace_type="admin",
            action=action,
            target_type=target_type,
            target_id=target_id,
            assisted=False,
            safe_metadata=metadata or {},
        )
    )


@router.get("/localizations", response_model=LocalizationPage)
def list_localizations(
    localization_status: str | None = Query(default=None, alias="status", pattern="^(generated|reviewed|approved|stale|failed)$"),
    language: str | None = None,
    resource_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    query = db.query(KnowledgeLocalization)
    if localization_status:
        query = query.filter(KnowledgeLocalization.status == localization_status)
    if language:
        query = query.filter(KnowledgeLocalization.language == language)
    if resource_type:
        query = query.filter(KnowledgeLocalization.resource_type == resource_type)
    total = query.count()
    rows = (
        query.order_by(KnowledgeLocalization.updated_at.desc(), KnowledgeLocalization.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return LocalizationPage(items=rows, total=total, skip=skip, limit=limit)


@router.post("/localizations/{localization_id}/review", response_model=LocalizationResponse)
def review_localization(
    localization_id: UUID,
    payload: LocalizationReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    row = _localization_or_404(db, localization_id)
    try:
        ContentLocalizationService.review(
            db,
            row,
            reviewer_id=admin.id,
            text=payload.text,
            lock=payload.lock,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "localization_review_invalid"}) from exc
    _audit(
        db,
        admin,
        action="localization_reviewed",
        target_type="knowledge_localization",
        target_id=str(row.id),
        metadata={"language": row.language, "resource_type": row.resource_type, "field_path": row.field_path},
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/localizations/{localization_id}/approve", response_model=LocalizationResponse)
def approve_localization(
    localization_id: UUID,
    payload: LocalizationReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    row = _localization_or_404(db, localization_id)
    try:
        ContentLocalizationService.approve(db, row, reviewer_id=admin.id, text=payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "localization_approval_invalid"}) from exc
    _audit(
        db,
        admin,
        action="localization_approved",
        target_type="knowledge_localization",
        target_id=str(row.id),
        metadata={"language": row.language, "resource_type": row.resource_type, "field_path": row.field_path},
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/localizations/{localization_id}/unlock", response_model=LocalizationResponse)
def unlock_localization(
    localization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    row = _localization_or_404(db, localization_id)
    ContentLocalizationService.unlock_for_regeneration(db, row)
    _audit(
        db,
        admin,
        action="localization_unlocked",
        target_type="knowledge_localization",
        target_id=str(row.id),
        metadata={"language": row.language, "resource_type": row.resource_type, "field_path": row.field_path},
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/localization-jobs", response_model=LocalizationJobPage)
def list_localization_jobs(
    job_status: str | None = Query(default=None, alias="status", pattern="^(pending|processing|retry|succeeded|failed|cancelled)$"),
    target_language: str | None = None,
    resource_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    query = db.query(LocalizationJob)
    if job_status:
        query = query.filter(LocalizationJob.status == job_status)
    if target_language:
        query = query.filter(LocalizationJob.target_language == target_language)
    if resource_type:
        query = query.filter(LocalizationJob.resource_type == resource_type)
    total = query.count()
    rows = query.order_by(LocalizationJob.id.desc()).offset(skip).limit(limit).all()
    return LocalizationJobPage(items=rows, total=total, skip=skip, limit=limit)


@router.post("/localization-jobs", response_model=LocalizationJobResponse, status_code=status.HTTP_201_CREATED)
def enqueue_localization_job(
    payload: LocalizationJobRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    if not settings.LOCALIZATION_ENABLED:
        raise HTTPException(status_code=409, detail={"code": "localization_disabled"})

    # Manual/reviewer-authored prose is a first-class locale variant. Store it
    # independently from the canonical provider row before using it to seed
    # machine translations for other locales.
    if payload.source_language != "auto":
        try:
            authored = ContentLocalizationService.author_source(
                db,
                resource_type=payload.resource_type,
                resource_key=payload.resource_key,
                field_path=payload.field_path,
                language=payload.source_language,
                text=payload.source_text,
                author_id=admin.id,
                entity_uuid=payload.entity_uuid,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": "localization_source_locked"}) from exc
        _audit(
            db,
            admin,
            action="localization_source_authored",
            target_type="knowledge_localization",
            target_id=str(authored.id),
            metadata={
                "resource_type": authored.resource_type,
                "field_path": authored.field_path,
                "language": authored.language,
            },
        )

    row = LocalizationQueueService.enqueue_field(
        db,
        resource_type=payload.resource_type,
        resource_key=payload.resource_key,
        field_path=payload.field_path,
        source_text=payload.source_text,
        source_language=payload.source_language,
        target_language=payload.target_language,
        entity_uuid=payload.entity_uuid,
        protected_terms=tuple(payload.protected_terms),
        context=payload.context,
        force=True,
    )
    if row is None:
        raise HTTPException(status_code=409, detail={"code": "localization_job_not_needed"})
    _audit(
        db,
        admin,
        action="localization_job_enqueued",
        target_type="localization_job",
        target_id=str(row.id),
        metadata={
            "resource_type": row.resource_type,
            "field_path": row.field_path,
            "source_language": row.source_language,
            "target_language": row.target_language,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/localization-backfill", response_model=LocalizationBackfillResponse)
def backfill_localizations(
    payload: LocalizationBackfillRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    if not settings.LOCALIZATION_ENABLED:
        raise HTTPException(status_code=409, detail={"code": "localization_disabled"})
    targets = tuple(payload.target_languages) if payload.target_languages else None
    try:
        result = LocalizationBackfillService.backfill(
            db,
            resource_type=payload.resource_type,
            after_id=payload.after_id,
            limit=payload.limit,
            source_language=payload.source_language,
            target_languages=targets,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "localization_backfill_invalid"}) from exc
    _audit(
        db,
        admin,
        action="localization_backfill_enqueued",
        target_type="localization_backfill",
        target_id=payload.resource_type,
        metadata={
            "source_language": payload.source_language,
            "target_languages": list(targets or settings.localization_target_languages),
            "scanned": result.scanned,
            "queued": result.queued,
            "after_id": payload.after_id,
            "next_cursor": result.next_cursor,
        },
    )
    db.commit()
    return LocalizationBackfillResponse(**result.__dict__)


@router.post("/localization-jobs/{job_id}/retry", response_model=LocalizationJobResponse)
def retry_localization_job(
    job_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    row = _job_or_404(db, job_id)
    if row.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail={"code": "localization_job_not_retryable"})
    row.status = "retry"
    row.attempt_count = 0
    row.next_attempt_at = datetime.now(UTC)
    row.lease_expires_at = None
    row.worker_id = None
    row.completed_at = None
    row.safe_failure_category = None
    _audit(
        db,
        admin,
        action="localization_job_retried",
        target_type="localization_job",
        target_id=str(row.id),
        metadata={"target_language": row.target_language, "resource_type": row.resource_type},
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/localization-jobs/{job_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_localization_job(
    job_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    row = _job_or_404(db, job_id)
    if row.status not in {"pending", "retry"}:
        raise HTTPException(status_code=409, detail={"code": "localization_job_not_cancellable"})
    row.status = "cancelled"
    row.completed_at = datetime.now(UTC)
    row.next_attempt_at = None
    _audit(
        db,
        admin,
        action="localization_job_cancelled",
        target_type="localization_job",
        target_id=str(row.id),
        metadata={"target_language": row.target_language, "resource_type": row.resource_type},
    )
    db.commit()


@router.get("/localization-diagnostics")
def localization_diagnostics(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    return LocalizationQueueService.diagnostics(db)
