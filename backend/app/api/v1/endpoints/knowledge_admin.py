"""Global-admin-only operational surface for durable knowledge jobs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_admin_user
from app.db.database import get_db
from app.knowledge.adapters import AdapterNotFoundError, KnowledgeAdapterRegistry
from app.knowledge.models import (
    ACTIVE_KNOWLEDGE_JOB_STATES,
    KNOWLEDGE_JOB_STATES,
    KNOWLEDGE_JOB_TRIGGERS,
    KnowledgeJob,
    KnowledgeProvider,
    KnowledgeWorkerHeartbeat,
)
from app.knowledge.schemas import (
    KnowledgeJobAttemptResponse,
    KnowledgeJobCreateRequest,
    KnowledgeJobCreatedResponse,
    KnowledgeJobDetailResponse,
    KnowledgeJobPage,
    KnowledgeJobResponse,
    KnowledgeProviderResponse,
    KnowledgeWorkerResponse,
)
from app.knowledge.services import (
    CompletedJobRecreationError,
    EnqueueKnowledgeJob,
    KnowledgeJobConflictError,
    KnowledgeJobNotFoundError,
    KnowledgeJobService,
    ProviderUnavailableForJobError,
)
from app.models.user import User
from app.models.workspace_audit import WorkspaceAudit


router = APIRouter()
adapters = KnowledgeAdapterRegistry()


def _job_response(job: KnowledgeJob) -> KnowledgeJobResponse:
    return KnowledgeJobResponse(
        id=job.id,
        provider_id=job.provider_id,
        job_type=job.job_type,
        entity_type=job.entity_type_id,
        scope=job.scope,
        priority=job.priority,
        state=job.state,
        scheduled_at=job.scheduled_at,
        claimed_at=job.claimed_at,
        lease_expires_at=job.lease_expires_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        worker_id=job.worker_id,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        parent_job_id=job.parent_job_id,
        correlation_id=job.correlation_id,
        last_error_code=job.last_error_code,
        safe_last_error=job.safe_last_error,
        trigger=job.trigger,
        created_at=job.created_at,
        updated_at=job.updated_at,
        can_retry=job.state == "failed" and job.attempt_count < job.max_attempts,
        can_cancel=job.state in ACTIVE_KNOWLEDGE_JOB_STATES,
    )


def _attempt_response(attempt) -> KnowledgeJobAttemptResponse:
    return KnowledgeJobAttemptResponse(
        id=attempt.id,
        attempt_number=attempt.attempt_number,
        worker_id=attempt.worker_id,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        outcome=attempt.outcome,
        retryable=attempt.retryable,
        error_code=attempt.error_code,
        safe_error=attempt.safe_error,
        metrics=attempt.metrics,
    )


def _job_or_404(db: Session, job_id: UUID) -> KnowledgeJob:
    job = db.get(KnowledgeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "knowledge_job_not_found"})
    return job


def _audit(db: Session, admin: User, action: str, job: KnowledgeJob, metadata: dict | None = None) -> None:
    db.add(
        WorkspaceAudit(
            actor_id=admin.id,
            workspace_type="admin",
            action=action,
            target_type="knowledge_job",
            target_id=str(job.id),
            assisted=False,
            safe_metadata={"provider_id": job.provider_id, "job_type": job.job_type, **(metadata or {})},
        )
    )


@router.get("/jobs", response_model=KnowledgeJobPage)
def list_jobs(
    provider_id: str | None = None,
    entity_type: str | None = None,
    state_filter: str | None = Query(default=None, alias="state"),
    trigger: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    if state_filter and state_filter not in KNOWLEDGE_JOB_STATES:
        raise HTTPException(status_code=400, detail={"code": "invalid_knowledge_job_state"})
    if trigger and trigger not in KNOWLEDGE_JOB_TRIGGERS:
        raise HTTPException(status_code=400, detail={"code": "invalid_knowledge_job_trigger"})
    query = db.query(KnowledgeJob)
    if provider_id:
        query = query.filter(KnowledgeJob.provider_id == provider_id)
    if entity_type:
        query = query.filter(KnowledgeJob.entity_type_id == entity_type)
    if state_filter:
        query = query.filter(KnowledgeJob.state == state_filter)
    if trigger:
        query = query.filter(KnowledgeJob.trigger == trigger)
    total = query.count()
    jobs = query.order_by(KnowledgeJob.created_at.desc()).offset(skip).limit(limit).all()
    return KnowledgeJobPage(items=[_job_response(job) for job in jobs], total=total, skip=skip, limit=limit)


@router.get("/jobs/{job_id}", response_model=KnowledgeJobDetailResponse)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    job = _job_or_404(db, job_id)
    return KnowledgeJobDetailResponse(
        **_job_response(job).model_dump(),
        attempts=[_attempt_response(attempt) for attempt in job.attempts],
    )


@router.post("/jobs", response_model=KnowledgeJobCreatedResponse, status_code=status.HTTP_201_CREATED)
def enqueue_job(
    payload: KnowledgeJobCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    provider = db.get(KnowledgeProvider, payload.provider_id)
    if provider is None:
        raise HTTPException(status_code=400, detail={"code": "knowledge_provider_unknown"})
    try:
        adapters.validate_enqueue(
            payload.provider_id,
            payload.job_type,
            payload.entity_type,
            payload.scope,
            payload.payload,
        )
    except AdapterNotFoundError as exc:
        raise HTTPException(status_code=400, detail={"code": "knowledge_adapter_unsupported"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "knowledge_job_input_invalid"}) from exc
    if payload.job_type in {"creature_catalog", "item_catalog", "quest_catalog"} and not payload.confirm_catalog_sync:
        raise HTTPException(status_code=400, detail={"code": "knowledge_catalog_confirmation_required"})
    try:
        result = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id=payload.provider_id,
                job_type=payload.job_type,
                entity_type=payload.entity_type,
                scope=payload.scope,
                payload=payload.payload,
                priority=payload.priority,
                scheduled_at=payload.scheduled_at,
                max_attempts=payload.max_attempts,
                created_by_id=admin.id,
                trigger="manual",
                allow_completed_recreate=payload.allow_completed_recreate,
            ),
        )
    except (ValueError, ProviderUnavailableForJobError) as exc:
        raise HTTPException(status_code=400, detail={"code": "knowledge_enqueue_invalid"}) from exc
    except CompletedJobRecreationError as exc:
        raise HTTPException(status_code=409, detail={"code": "knowledge_job_completed"}) from exc
    _audit(db, admin, "knowledge_job_enqueued", result.job, {"created": result.created})
    db.commit()
    db.refresh(result.job)
    return KnowledgeJobCreatedResponse(item=_job_response(result.job), created=result.created)


@router.post("/jobs/{job_id}/retry", response_model=KnowledgeJobResponse)
def retry_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    try:
        job = KnowledgeJobService.manual_retry(db, job_id)
    except KnowledgeJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "knowledge_job_not_found"}) from exc
    except KnowledgeJobConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": "knowledge_job_retry_conflict"}) from exc
    _audit(db, admin, "knowledge_job_retried", job)
    db.commit()
    db.refresh(job)
    return _job_response(job)


@router.post("/jobs/{job_id}/cancel", response_model=KnowledgeJobResponse)
def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    try:
        job = KnowledgeJobService.cancel(db, job_id)
    except KnowledgeJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "knowledge_job_not_found"}) from exc
    except KnowledgeJobConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": "knowledge_job_cancel_conflict"}) from exc
    _audit(db, admin, "knowledge_job_cancelled", job)
    db.commit()
    db.refresh(job)
    return _job_response(job)


@router.get("/workers", response_model=list[KnowledgeWorkerResponse])
def list_workers(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    workers = db.query(KnowledgeWorkerHeartbeat).order_by(KnowledgeWorkerHeartbeat.last_seen_at.desc()).all()
    return [KnowledgeWorkerResponse.model_validate(worker, from_attributes=True) for worker in workers]


@router.get("/providers", response_model=list[KnowledgeProviderResponse])
def list_providers(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    providers = db.query(KnowledgeProvider).order_by(KnowledgeProvider.priority, KnowledgeProvider.provider_id).all()
    return [
        KnowledgeProviderResponse(
            provider_id=provider.provider_id,
            provider_name=provider.provider_name,
            priority=provider.priority,
            enabled=provider.enabled,
            version=provider.version,
            health=provider.health,
            last_attempted_at=provider.last_attempted_at,
            last_success_at=provider.last_success_at,
            last_failure_at=provider.last_failure_at,
            consecutive_failures=provider.consecutive_failures,
            cooldown_until=provider.cooldown_until,
            supports_entities=list(provider.supports_entities),
            supports_media=provider.supports_media,
            supports_search=provider.supports_search,
            supported_job_types=adapters.supported_job_types(provider.provider_id, list(provider.supports_entities)),
        )
        for provider in providers
    ]
