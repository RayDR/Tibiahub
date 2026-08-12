"""Safe, moderated Hunt Analyzer ingestion and robust public aggregates."""
from __future__ import annotations
import json
from datetime import UTC, datetime
from statistics import median, quantiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.v1.endpoints.auth import get_current_admin_user, get_current_user
from app.db.database import get_db
from app.models.hunt_analyzer import HuntAnalyzerSubmission
from app.models.user import User
from app.services.text_utils import normalize_search_text

router = APIRouter(prefix="/hunt-analyzer", tags=["Hunt Analyzer"])


class AnalyzerPaste(BaseModel):
    payload: dict


class ModerationInput(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=5, max_length=1000)


def _number(payload: dict, *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return None


def _validate(payload: dict) -> dict:
    zone = str(payload.get("hunt_name") or payload.get("zone_name") or payload.get("hunt") or "").strip()
    duration = _number(payload, "duration_seconds", "duration")
    raw_exp = _number(payload, "raw_exp", "xp_gain", "experience")
    profit = _number(payload, "profit", "balance")
    if not zone or len(zone) > 255 or duration is None or not 60 <= duration <= 86400 or raw_exp is None or raw_exp < 0 or profit is None or abs(profit) > 2_000_000_000:
        raise HTTPException(status_code=422, detail="Hunt Analyzer payload is missing valid Hunt, duration, Raw EXP, or Profit values")
    return {"zone_name": zone, "normalized_zone": normalize_search_text(zone), "duration_seconds": duration, "raw_exp": raw_exp, "profit": profit}


def _store(payload: dict, source_kind: str, user: User, db: Session):
    record = HuntAnalyzerSubmission(**_validate(payload), source_kind=source_kind, source_payload=payload, submitted_by_id=user.id, moderation_status="pending")
    db.add(record); db.commit(); db.refresh(record)
    return {"id": record.id, "moderation_status": record.moderation_status, "authoritative": False}


@router.post("/submissions")
def paste_submission(body: AnalyzerPaste, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(json.dumps(body.payload)) > 262_144:
        raise HTTPException(status_code=413, detail="Hunt Analyzer payload is too large")
    return _store(body.payload, "paste", user, db)


@router.post("/submissions/upload")
async def upload_submission(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content = await file.read(262_145)
    if len(content) > 262_144:
        raise HTTPException(status_code=413, detail="Hunt Analyzer file is too large")
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=422, detail="File must contain one valid JSON object")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="File must contain one JSON object")
    return _store(payload, "upload", user, db)


@router.patch("/submissions/{submission_id}/moderation")
def moderate(submission_id: int, body: ModerationInput, admin: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    record = db.get(HuntAnalyzerSubmission, submission_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    record.moderation_status = body.status; record.moderation_reason = body.reason
    record.moderated_by_id = admin.id; record.moderated_at = datetime.now(UTC); db.commit()
    return {"id": record.id, "moderation_status": record.moderation_status, "authoritative": False}


@router.get("/aggregates")
def aggregates(zone: str = Query(..., min_length=2, max_length=255), db: Session = Depends(get_db)):
    rows = db.query(HuntAnalyzerSubmission).filter_by(normalized_zone=normalize_search_text(zone), moderation_status="approved").all()
    if len(rows) < 3:
        return {"zone": zone, "sample_count": len(rows), "available": False, "authoritative": False}
    exp_rates = sorted(row.raw_exp * 3600 / row.duration_seconds for row in rows)
    profit_rates = sorted(row.profit * 3600 / row.duration_seconds for row in rows)
    def stats(values: list[float]):
        q1, _, q3 = quantiles(values, n=4, method="inclusive")
        trim = int(len(values) * .1); trimmed = values[trim:len(values)-trim] if trim else values
        return {"median": round(median(values)), "q1": round(q1), "q3": round(q3), "trimmed_mean": round(sum(trimmed) / len(trimmed))}
    return {"zone": rows[0].zone_name, "sample_count": len(rows), "available": True, "raw_exp_per_hour": stats(exp_rates), "profit_per_hour": stats(profit_rates), "authoritative": False}
