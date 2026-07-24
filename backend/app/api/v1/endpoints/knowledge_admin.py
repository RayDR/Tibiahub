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
    KnowledgeEntity,
    KnowledgeProvider,
    KnowledgeRelationship,
    SpatialEntityLocationLink,
    SpatialMapPoint,
    SpatialMapRegion,
    SpatialRoute,
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
    KnowledgeGraphReviewItem,
    KnowledgeGraphReviewPage,
    KnowledgeProvenanceResponse,
    KnowledgeRelationshipAction,
)
from app.knowledge.services import (
    CompletedJobRecreationError,
    EnqueueKnowledgeJob,
    KnowledgeJobConflictError,
    KnowledgeJobNotFoundError,
    KnowledgeJobService,
    KnowledgeGraphService,
    ProviderUnavailableForJobError,
)
from app.knowledge.registry import RelationshipTypeRegistry
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


def _relationship_or_404(db: Session, relationship_id: UUID) -> KnowledgeRelationship:
    relationship = db.get(KnowledgeRelationship, relationship_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail={"code": "knowledge_relationship_not_found"})
    return relationship


def _relationship_audit(db: Session, admin: User, action: str, relationship: KnowledgeRelationship) -> None:
    db.add(WorkspaceAudit(
        actor_id=admin.id, workspace_type="admin", action=action,
        target_type="knowledge_relationship", target_id=str(relationship.id), assisted=False,
        safe_metadata={"relationship_type": relationship.relationship_type_code,
                       "resolution_state": relationship.resolution_state},
    ))


def _spatial_audit(db: Session, admin: User, action: str, kind: str, record_id: UUID) -> None:
    db.add(WorkspaceAudit(
        actor_id=admin.id, workspace_type="admin", action=action,
        target_type=f"spatial_{kind}", target_id=str(record_id), assisted=False,
        safe_metadata={"kind": kind},
    ))


def _review_item(db: Session, relationship: KnowledgeRelationship) -> KnowledgeGraphReviewItem:
    candidates = []
    for raw_id in (relationship.source_context or {}).get("candidate_entity_ids", []):
        try:
            entity = db.get(KnowledgeEntity, UUID(str(raw_id)))
        except (TypeError, ValueError):
            entity = None
        try:
            valid = bool(entity and RelationshipTypeRegistry.validate(
                db, relationship.relationship_type_code,
                relationship.source_entity.entity_type, entity.entity_type,
            ))
        except ValueError:
            valid = False
        if valid:
            candidates.append({"id": str(entity.uuid), "name": entity.canonical_name,
                               "type": entity.entity_type, "slug": entity.slug or ""})
    return KnowledgeGraphReviewItem(
        id=relationship.id, source_entity_id=relationship.source_entity_id,
        source_name=relationship.source_entity.canonical_name,
        source_type=relationship.source_entity.entity_type, source_scope=relationship.source_scope,
        relationship_type=relationship.relationship_type_code,
        target_type=relationship.target_entity_type_id or "unknown",
        target_name=relationship.target_entity.canonical_name if relationship.target_entity else None,
        unresolved_name=relationship.unresolved_name,
        resolution_state=relationship.resolution_state, confidence=relationship.confidence,
        provider_id=relationship.source_provider_id, document_id=relationship.source_document_id,
        candidates=candidates, created_at=relationship.created_at,
    )


@router.get("/relationships/review", response_model=KnowledgeGraphReviewPage)
def review_relationships(
    resolution_state: str = Query("unresolved", pattern="^(resolved|unresolved|ambiguous)$"),
    relationship_type: str | None = None, provider_id: str | None = None,
    skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user),
):
    query = db.query(KnowledgeRelationship).filter_by(
        resolution_state=resolution_state, is_current=True,
    )
    if relationship_type:
        query = query.filter_by(relationship_type_code=relationship_type)
    if provider_id:
        query = query.filter_by(source_provider_id=provider_id)
    total = query.count()
    rows = query.order_by(KnowledgeRelationship.created_at.desc()).offset(skip).limit(limit).all()
    return KnowledgeGraphReviewPage(items=[_review_item(db, row) for row in rows], total=total, skip=skip, limit=limit)


@router.get("/relationships/{relationship_id}/provenance", response_model=KnowledgeProvenanceResponse)
def relationship_provenance(relationship_id: UUID, db: Session = Depends(get_db),
                            _admin: User = Depends(get_current_admin_user)):
    row = _relationship_or_404(db, relationship_id)
    safe_keys = {"source_document_ref", "direction", "compatibility_table", "reason", "verification_reason"}
    return KnowledgeProvenanceResponse(
        relationship_id=row.id, provider_id=row.source_provider_id, document_id=row.source_document_id,
        job_id=row.source_job_id, confidence=row.confidence, manual_override=row.manual_override,
        verified_at=row.verified_at, valid_from=row.valid_from, valid_until=row.valid_until,
        is_current=row.is_current, superseded_by_id=row.superseded_by_id,
        safe_context={key: value for key, value in (row.source_context or {}).items() if key in safe_keys},
    )


@router.post("/relationships/{relationship_id}/resolve", response_model=KnowledgeGraphReviewItem)
def resolve_relationship(relationship_id: UUID, payload: KnowledgeRelationshipAction,
                         db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    if payload.target_entity_id is None:
        raise HTTPException(status_code=400, detail={"code": "knowledge_resolution_target_required"})
    old = _relationship_or_404(db, relationship_id)
    try:
        row = KnowledgeGraphService.resolve_reference(
            db, old, payload.target_entity_id, admin_id=admin.id, reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "knowledge_resolution_invalid"}) from exc
    _relationship_audit(db, admin, "knowledge_relationship_resolved", row)
    db.commit(); db.refresh(row)
    return _review_item(db, row)


@router.post("/relationships/{relationship_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_relationship(relationship_id: UUID, payload: KnowledgeRelationshipAction,
                        db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    row = _relationship_or_404(db, relationship_id)
    try:
        KnowledgeGraphService.reject(db, row, admin_id=admin.id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "knowledge_relationship_not_current"}) from exc
    _relationship_audit(db, admin, "knowledge_relationship_rejected", row)
    db.commit()


@router.post("/relationships/{relationship_id}/verify", response_model=KnowledgeGraphReviewItem)
def verify_relationship(relationship_id: UUID, payload: KnowledgeRelationshipAction,
                        db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    row = _relationship_or_404(db, relationship_id)
    try:
        KnowledgeGraphService.verify(db, row, admin_id=admin.id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "knowledge_relationship_not_resolved"}) from exc
    _relationship_audit(db, admin, "knowledge_relationship_verified", row)
    db.commit(); db.refresh(row)
    return _review_item(db, row)


@router.post("/relationships/{relationship_id}/supersede", status_code=status.HTTP_204_NO_CONTENT)
def supersede_relationship(relationship_id: UUID, payload: KnowledgeRelationshipAction,
                           db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    row = _relationship_or_404(db, relationship_id)
    if not row.is_current:
        raise HTTPException(status_code=409, detail={"code": "knowledge_relationship_not_current"})
    row.rejection_reason = payload.reason
    KnowledgeGraphService.supersede(db, row)
    _relationship_audit(db, admin, "knowledge_relationship_superseded", row)
    db.commit()


@router.get("/spatial/review")
def review_spatial(
    kind: str = Query("point", pattern="^(point|region|route|link)$"),
    verification_state: str = Query("unresolved", pattern="^(pending|verified|rejected|unresolved|ambiguous)$"),
    skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), _admin: User = Depends(get_current_admin_user),
):
    models = {
        "point": SpatialMapPoint,
        "region": SpatialMapRegion,
        "route": SpatialRoute,
        "link": SpatialEntityLocationLink,
    }
    model = models[kind]
    query = db.query(model).filter_by(verification_state=verification_state, is_current=True)
    total = query.count()
    rows = query.order_by(model.created_at.desc()).offset(skip).limit(limit).all()
    return {"items": [{
        "id": row.id, "name": getattr(row, "name", None), "external_id": row.external_id,
        "location_entity_id": getattr(row, "location_entity_id", None),
        "source_entity_id": getattr(row, "source_entity_id", None),
        "unresolved_location_name": getattr(row, "unresolved_location_name", None),
        "unresolved_references": [value for value in (
            getattr(row, "unresolved_location_name", None),
            getattr(row, "unresolved_start_name", None),
            getattr(row, "unresolved_end_name", None),
        ) if value],
        "confidence": row.confidence, "verification_state": row.verification_state,
        "provider_id": row.source_provider_id, "version": row.version,
    } for row in rows], "total": total, "skip": skip, "limit": limit}


def _spatial_record(db: Session, kind: str, record_id: UUID):
    model = SpatialMapPoint if kind == "points" else SpatialMapRegion
    row = db.get(model, record_id)
    if row is None or not row.is_current:
        raise HTTPException(status_code=404, detail={"code": "spatial_record_not_found"})
    return row


@router.post("/spatial/{kind}/{record_id}/verify")
def verify_spatial(kind: str, record_id: UUID, payload: KnowledgeRelationshipAction,
                   db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    if kind not in {"points", "regions"}:
        raise HTTPException(status_code=404, detail={"code": "spatial_record_not_found"})
    row = _spatial_record(db, kind, record_id)
    if row.verification_state in {"rejected", "unresolved", "ambiguous"}:
        raise HTTPException(status_code=409, detail={"code": "spatial_record_not_verifiable"})
    from datetime import UTC, datetime
    row.verification_state = "verified"; row.confidence = "verified"
    row.verified_by_id = admin.id; row.verified_at = datetime.now(UTC)
    row.rejection_reason = None
    _spatial_audit(db, admin, "spatial_record_verified", kind, row.id)
    db.commit()
    return {"id": row.id, "verification_state": row.verification_state, "confidence": row.confidence}


@router.post("/spatial/{kind}/{record_id}/reject")
def reject_spatial(kind: str, record_id: UUID, payload: KnowledgeRelationshipAction,
                   db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    if kind not in {"points", "regions"}:
        raise HTTPException(status_code=404, detail={"code": "spatial_record_not_found"})
    row = _spatial_record(db, kind, record_id)
    from datetime import UTC, datetime
    row.verification_state = "rejected"; row.rejection_reason = payload.reason
    row.verified_by_id = admin.id; row.verified_at = datetime.now(UTC)
    _spatial_audit(db, admin, "spatial_record_rejected", kind, row.id)
    db.commit()
    return {"id": row.id, "verification_state": row.verification_state}


@router.get("/spatial/routes/{route_id}/provenance")
def route_provenance(route_id: UUID, db: Session = Depends(get_db),
                     _admin: User = Depends(get_current_admin_user)):
    row = db.get(SpatialRoute, route_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "spatial_route_not_found"})
    return {
        "id": row.id, "provider_id": row.source_provider_id,
        "document_id": row.source_document_id, "job_id": row.source_job_id,
        "source_reference": row.source_reference, "confidence": row.confidence,
        "verification_state": row.verification_state, "version": row.version,
        "is_current": row.is_current, "valid_from": row.valid_from, "valid_until": row.valid_until,
        "step_count": row.step_count,
    }


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
    if payload.job_type in {"creature_catalog", "item_catalog", "quest_catalog", "npc_catalog", "location_catalog"} and not payload.confirm_catalog_sync:
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
