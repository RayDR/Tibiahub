#!/usr/bin/env python3
import sys
sys.path.append('/forge/tibiahub/backend')

from app.db.database import SessionLocal
from app.models.events import Event, PublicEventParticipant
from sqlalchemy import func

db = SessionLocal()

event_id = 3

# Test 1: Ver datos existentes
print("=== Current Participants ===")
participants = db.query(PublicEventParticipant).filter(
    PublicEventParticipant.event_id == event_id
).all()

for p in participants:
    print(f"ID:{p.id} - {p.character_name} - #{p.assigned_number}")

print(f"\nTotal: {len(participants)}")

# Test 2: Ver max
print("\n=== Testing func.max ===")
current_max = db.query(func.max(PublicEventParticipant.assigned_number)).filter(
    PublicEventParticipant.event_id == event_id
).scalar()

print(f"Current max: {current_max}")
print(f"Next number would be: {(current_max + 1) if current_max else 1}")

db.close()
