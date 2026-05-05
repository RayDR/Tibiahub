"""
Events and Raffles Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
import random
from datetime import datetime

from app.db.database import get_db
from app.models.events import Event, EventParticipant, PublicEventParticipant
from app.models.user import User
from app.schemas.events import (
    Event as EventSchema,
    EventCreate,
    EventUpdate,
    DrawWinnerResponse,
    EventParticipant as ParticipantSchema,
    PublicParticipantCreate,
    PublicParticipant as PublicParticipantSchema
)
from app.api.v1.endpoints.auth import get_current_user, get_current_admin_user
from app.api.v1.endpoints.auth import get_current_manager_user
from app.core.permissions import can_manage_guild, is_global_admin

from app.services.tibia_api import get_active_guild_members, get_character_info, get_guild_info
from app.services.public_code import generate_unique_code
import asyncio

router = APIRouter()


def _require_event_management(current_user: User, event: Event) -> None:
    if can_manage_guild(current_user, event.guild_name):
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions for this guild event")


def _is_event_registration_open(event: Event) -> bool:
    if event.is_deleted or event.status in {"archived", "deleted"}:
        return False
    if event.status != "active":
        return False
    if not event.registration_enabled:
        return False
    return True


@router.get("/", response_model=List[EventSchema])
def get_events(
    status: Optional[str] = None,
    type: Optional[str] = None,
    guild_name: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all events with optional filtering"""
    query = db.query(Event).filter(Event.is_active == True)
    query = query.filter(Event.is_deleted == False)
    
    if status:
        query = query.filter(Event.status == status)
    if type:
        query = query.filter(Event.type == type)

    requested_guild = (guild_name or "").strip()
    if is_global_admin(current_user):
        if requested_guild:
            query = query.filter(func.lower(Event.guild_name) == requested_guild.lower())
    else:
        own_guild = (current_user.guild_name or "").strip()
        if not own_guild:
            return []
        query = query.filter(func.lower(Event.guild_name) == own_guild.lower())
    
    events = query.order_by(desc(Event.created_at)).offset(skip).limit(limit).all()
    
    # Enrich with creator and winner names
    result = []
    for event in events:
        event_dict = EventSchema.from_orm(event).dict()
        event_dict['creator_name'] = event.creator.username if event.creator else None
        event_dict['winner_name'] = event.winner.username if event.winner else None
        event_dict['participant_count'] = len(event.participants)
        
        # Get participants with usernames
        participants = []
        for p in event.participants:
            p_dict = ParticipantSchema.from_orm(p).dict()
            p_dict['username'] = p.user.username if p.user else None
            participants.append(ParticipantSchema(**p_dict))
        
        event_dict['participants'] = participants
        result.append(EventSchema(**event_dict))
    
    return result


@router.get("/{event_id}", response_model=EventSchema)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific event"""
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True, Event.is_deleted == False).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event_dict = EventSchema.from_orm(event).dict()
    event_dict['creator_name'] = event.creator.username if event.creator else None
    event_dict['winner_name'] = event.winner.username if event.winner else None
    
    # For public events, use public_event_participants
    if event.is_public:
        public_participants = db.query(PublicEventParticipant).filter(
            PublicEventParticipant.event_id == event_id,
            PublicEventParticipant.is_excluded == False  # Don't show excluded participants
        ).order_by(PublicEventParticipant.assigned_number).all()
        
        event_dict['participant_count'] = len(public_participants)
        participants = []
        for p in public_participants:
            participants.append({
                'id': p.id,
                'event_id': p.event_id,
                'user_id': None,
                'username': p.character_name,
                'assigned_number': p.assigned_number,
                'joined_at': p.created_at.isoformat() if p.created_at else None
            })
        event_dict['participants'] = participants
    else:
        # For private events, use internal participants
        event_dict['participant_count'] = len(event.participants)
        participants = []
        for p in event.participants:
            p_dict = ParticipantSchema.from_orm(p).dict()
            p_dict['username'] = p.user.username if p.user else None
            participants.append(ParticipantSchema(**p_dict))
        event_dict['participants'] = participants
    
    return EventSchema(**event_dict)


@router.post("/", response_model=EventSchema, status_code=status.HTTP_201_CREATED)
def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """Create a new event (admin only)"""
    new_event = Event(
        **event.dict(),
        public_code=generate_unique_code(db, Event),
        creator_id=current_user.id
    )
    
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    event_dict = EventSchema.from_orm(new_event).dict()
    event_dict['creator_name'] = current_user.username
    event_dict['participant_count'] = 0
    event_dict['participants'] = []
    
    return EventSchema(**event_dict)


@router.put("/{event_id}", response_model=EventSchema)
def update_event(
    event_id: int,
    event_update: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """Update an event (admin only)"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    
    update_data = event_update.dict(exclude_unset=True)
    if "status" in update_data and update_data["status"] not in {"active", "disabled", "completed", "archived", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid event status")
    if "archive_after_days" in update_data and update_data["archive_after_days"] is not None:
        update_data["archive_after_days"] = max(1, min(365, update_data["archive_after_days"]))
    for key, value in update_data.items():
        setattr(event, key, value)
    
    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    
    return get_event(event_id, db, current_user)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """Soft-delete an event (admin global or leader of its guild)."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    
    event.is_active = False
    event.is_deleted = True
    event.deleted_at = datetime.utcnow()
    event.deleted_by_user_id = current_user.id
    event.delete_reason = reason
    event.status = 'deleted'
    db.commit()
    return


@router.post("/{event_id}/restore", response_model=EventSchema)
def restore_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    event.is_active = True
    event.is_deleted = False
    event.deleted_at = None
    event.deleted_by_user_id = None
    event.delete_reason = None
    event.status = 'active'
    db.commit()
    db.refresh(event)
    return get_event(event_id, db, current_user)


@router.post("/{event_id}/join", response_model=ParticipantSchema)
def join_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Join an event"""
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _is_event_registration_open(event):
        raise HTTPException(status_code=400, detail="Event registration is closed")

    if event.is_public is False and event.guild_name and (current_user.guild_name or "").strip().lower() != event.guild_name.strip().lower() and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Private event restricted to guild members")
    
    if event.status != 'active':
        raise HTTPException(status_code=400, detail="Event is not active")
    
    # Check if already joined
    existing = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already joined this event")
    
    # Check if event is full
    if event.total_slots:
        current_count = db.query(EventParticipant).filter(EventParticipant.event_id == event_id).count()
        if current_count >= event.total_slots:
            raise HTTPException(status_code=400, detail="Event is full")
    
    # Assign number for raffle
    assigned_number = None
    if event.type == 'raffle':
        existing_numbers = [p.assigned_number for p in event.participants if p.assigned_number is not None]
        if event.total_slots:
            available_numbers = [n for n in range(1, event.total_slots + 1) if n not in existing_numbers]
            if available_numbers:
                assigned_number = random.choice(available_numbers)
        else:
            assigned_number = len(existing_numbers) + 1
    
    participant = EventParticipant(
        event_id=event_id,
        user_id=current_user.id,
        assigned_number=assigned_number
    )
    
    db.add(participant)
    db.commit()
    db.refresh(participant)
    
    p_dict = ParticipantSchema.from_orm(participant).dict()
    p_dict['username'] = current_user.username
    
    return ParticipantSchema(**p_dict)


@router.post("/{event_id}/draw", response_model=DrawWinnerResponse)
def draw_winner(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """Draw a winner for a raffle (admin only)"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    
    if event.is_drawn:
        raise HTTPException(status_code=400, detail="Winner already drawn")
    
    # Check if event is public and has public participants
    if event.is_public and event.public_participants:
        # Filter out excluded participants
        eligible_participants = [p for p in event.public_participants if not p.is_excluded]
        
        if not eligible_participants:
            raise HTTPException(status_code=400, detail="No eligible participants in this event")
        
        # Select random winner from eligible participants
        winner_participant = random.choice(eligible_participants)
        
        event.winner_id = None  # No user_id for external participants
        event.winner_number = winner_participant.assigned_number
        event.is_drawn = True
        event.status = 'completed'
        event.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(event)
        
        return DrawWinnerResponse(
            success=True,
            winner_id=0,  # Placeholder for external winners
            winner_name=winner_participant.character_name,
            winner_number=event.winner_number,
            total_participants=len(eligible_participants)
        )
    else:
        # Regular private event with registered users
        if not event.participants:
            raise HTTPException(status_code=400, detail="No participants in this event")
        
        # Select random winner
        winner_participant = random.choice(event.participants)
        
        event.winner_id = winner_participant.user_id
        event.winner_number = winner_participant.assigned_number
        event.is_drawn = True
        event.status = 'completed'
        event.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(event)
        
        return DrawWinnerResponse(
            success=True,
            winner_id=event.winner_id,
            winner_name=event.winner.username,
            winner_number=event.winner_number,
            total_participants=len(event.participants)
        )


@router.post("/{event_id}/participants/manual", response_model=PublicParticipantSchema)
async def add_manual_participant(
    event_id: int,
    participant_data: PublicParticipantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """Add a manual participant to a public event (admin only)"""
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    
    if not event.is_public:
        raise HTTPException(status_code=400, detail="Can only add manual participants to public events")
    
    if event.status != 'active':
        raise HTTPException(status_code=400, detail="Event is not active")
    
    # Validate character with TibiaData API
    try:
        char_info = await get_character_info(participant_data.character_name)
        if not char_info:
            raise HTTPException(status_code=404, detail=f"Character '{participant_data.character_name}' not found in Tibia")
        
        # Validate world restriction if set
        if event.guild_world and char_info.get('world') != event.guild_world:
            raise HTTPException(
                status_code=400, 
                detail=f"Character must be from world '{event.guild_world}' (character is from '{char_info.get('world')}')"
            )
        
        # Check if already exists
        existing = db.query(PublicEventParticipant).filter(
            PublicEventParticipant.event_id == event_id,
            PublicEventParticipant.character_name == char_info['name']
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"Character '{char_info['name']}' is already a participant")
        
        # Check if event is full
        if event.total_slots:
            current_count = db.query(PublicEventParticipant).filter(
                PublicEventParticipant.event_id == event_id
            ).count()
            if current_count >= event.total_slots:
                raise HTTPException(status_code=400, detail="Event is full")
        
        # Assign number for raffle
        assigned_number = None
        if event.type == 'raffle':
            # Get max number from DB
            current_max = db.query(func.max(PublicEventParticipant.assigned_number)).filter(
                PublicEventParticipant.event_id == event_id
            ).scalar()
            assigned_number = (current_max + 1) if current_max else 1
        
        # Create participant
        participant = PublicEventParticipant(
            event_id=event_id,
            character_name=char_info['name'],
            character_level=char_info.get('level'),
            character_vocation=char_info.get('vocation'),
            character_world=char_info.get('world'),
            last_login=char_info.get('last_login'),
            assigned_number=assigned_number,
            is_auto_loaded=False
        )
        
        db.add(participant)
        db.commit()
        db.refresh(participant)
        
        return PublicParticipantSchema.from_orm(participant)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating character: {str(e)}")


@router.post("/{event_id}/participants/load-guild")
async def load_guild_participants(
    event_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """Load participants from guild automatically (admin only)"""
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    
    if not event.is_public:
        raise HTTPException(status_code=400, detail="Can only load guild participants for public events")
    
    if event.participant_mode != 'guild_auto':
        raise HTTPException(status_code=400, detail="Event is not configured for automatic guild loading")
    
    if not event.guild_name:
        raise HTTPException(status_code=400, detail="No guild name configured for this event")
    
    # Get guild world if not set
    if not event.guild_world:
        try:
            guild_info = await get_guild_info(event.guild_name)
            if guild_info and guild_info.get('world'):
                event.guild_world = guild_info['world']
                db.commit()
        except Exception as e:
            print(f"Warning: Could not fetch guild world: {e}")
    
    try:
        # Get active members
        active_members = await get_active_guild_members(event.guild_name, event.active_days_limit)
        
        if not active_members:
            return {
                "success": True,
                "message": "No active members found",
                "loaded": 0,
                "updated": 0,
                "total": 0
            }
        
        loaded_count = 0
        updated_count = 0
        
        # Clear existing auto-loaded participants if force reload (except excluded ones)
        if force:
            db.query(PublicEventParticipant).filter(
                PublicEventParticipant.event_id == event_id,
                PublicEventParticipant.is_auto_loaded == True,
                PublicEventParticipant.is_excluded == False  # Keep excluded participants
            ).delete()
            db.commit()
        
        # Get starting number for new participants
        starting_number = 1
        if event.type == 'raffle':
            current_max = db.query(func.max(PublicEventParticipant.assigned_number)).filter(
                PublicEventParticipant.event_id == event_id
            ).scalar()
            starting_number = (current_max + 1) if current_max else 1
        
        new_participant_count = 0
        
        for member in active_members:
            # Check if already exists
            existing = db.query(PublicEventParticipant).filter(
                PublicEventParticipant.event_id == event_id,
                PublicEventParticipant.character_name == member['name']
            ).first()
            
            # Skip if user is excluded by admin
            if existing and existing.is_excluded:
                continue
            
            if existing:
                # Update existing participant data
                existing.character_level = member.get('level')
                existing.character_vocation = member.get('vocation')
                existing.character_world = member.get('world', event.guild_world)
                existing.last_login = member.get('last_login')
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Check slots
                if event.total_slots:
                    current_count = db.query(PublicEventParticipant).filter(
                        PublicEventParticipant.event_id == event_id
                    ).count()
                    if current_count >= event.total_slots:
                        break
                
                # Assign number using counter
                assigned_number = None
                if event.type == 'raffle':
                    assigned_number = starting_number + new_participant_count
                    new_participant_count += 1
                
                # Create new participant
                participant = PublicEventParticipant(
                    event_id=event_id,
                    character_name=member['name'],
                    character_level=member.get('level'),
                    character_vocation=member.get('vocation'),
                    character_world=member.get('world', event.guild_world),
                    last_login=member.get('last_login'),
                    assigned_number=assigned_number,
                    is_auto_loaded=True
                )
                db.add(participant)
                loaded_count += 1
        
        db.commit()
        
        total = db.query(PublicEventParticipant).filter(
            PublicEventParticipant.event_id == event_id
        ).count()
        
        return {
            "success": True,
            "message": f"Successfully loaded guild participants",
            "loaded": loaded_count,
            "updated": updated_count,
            "total": total
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading guild participants: {str(e)}")

@router.get("/public/{uuid}", response_model=EventSchema)
def get_public_event(
    uuid: str,
    db: Session = Depends(get_db)
):
    """Get a specific event (Public) by UUID"""
    event = db.query(Event).filter(Event.uuid == uuid, Event.is_active == True, Event.is_deleted == False).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    if not event.is_public:
        raise HTTPException(status_code=403, detail="This event is not public.")
    
    event_dict = EventSchema.from_orm(event).dict()
    event_dict['creator_name'] = event.creator.username if event.creator else None
    event_dict['winner_name'] = event.winner.username if event.winner else None
    
    # Get public participants
    public_participants = db.query(PublicEventParticipant).filter(
        PublicEventParticipant.event_id == event.id,
        PublicEventParticipant.is_deleted == False,
    ).order_by(PublicEventParticipant.assigned_number).all()
    
    event_dict['participant_count'] = len(public_participants)
    participants = []
    for p in public_participants:
        participants.append({
            'id': p.id,
            'event_id': p.event_id,
            'user_id': None,
            'username': p.character_name,
            'assigned_number': p.assigned_number,
            'joined_at': p.created_at.isoformat() if p.created_at else None
        })
    event_dict['participants'] = participants
        
    return EventSchema(**event_dict)


@router.get("/public/code/{public_code}", response_model=EventSchema)
def get_public_event_by_code(
    public_code: str,
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.public_code == public_code, Event.is_active == True, Event.is_deleted == False).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not event.is_public:
        raise HTTPException(status_code=403, detail="This event is not public")
    return get_public_event(event.uuid, db)


@router.get("/{event_id}/share")
def share_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    if event.type == "contest":
        return {"public_code": event.public_code, "url": f"https://tibiahub.domoforge.com/contests/{event.public_code}"}
    return {"public_code": event.public_code, "url": f"https://tibiahub.domoforge.com/public/event/{event.uuid}"}

@router.get("/{uuid}/raffle/status")
async def get_raffle_status(
    uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get raffle status including winner if drawn via UUID.
    Does NOT require auth. For public events, auto-syncs participants if needed.
    """
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.is_deleted:
        raise HTTPException(status_code=404, detail="Event not found")

    participants = []
    winner_name = None
    
    # For public events with guild_auto mode, sync participants if event is still active
    if event.is_public and event.participant_mode == 'guild_auto' and not event.is_drawn:
        if event.guild_name and event.draw_date:
            # Check if we're still before the draw date
            now = datetime.utcnow()
            draw_time = event.draw_date
            
            # Sync participants if we're within the event period
            if now < draw_time:
                try:
                    # Load participants from guild
                    active_members = await get_active_guild_members(event.guild_name, event.active_days_limit)
                    
                    # Get starting number for new participants (if raffle)
                    starting_number = 1
                    if event.type == 'raffle':
                        current_max = db.query(func.max(PublicEventParticipant.assigned_number)).filter(
                            PublicEventParticipant.event_id == event.id
                        ).scalar()
                        starting_number = (current_max + 1) if current_max else 1
                    
                    new_participant_count = 0
                    
                    # Update or create participants
                    for member in active_members:
                        existing = db.query(PublicEventParticipant).filter(
                            PublicEventParticipant.event_id == event.id,
                            PublicEventParticipant.character_name == member['name']
                        ).first()
                        
                        # Skip if user is excluded by admin
                        if existing and existing.is_excluded:
                            continue
                        
                        if existing:
                            # Update data
                            existing.character_level = member.get('level')
                            existing.character_vocation = member.get('vocation')
                            existing.last_login = member.get('last_login')
                            existing.updated_at = datetime.utcnow()
                        else:
                            # Check slots
                            if event.total_slots:
                                current_count = db.query(PublicEventParticipant).filter(
                                    PublicEventParticipant.event_id == event.id
                                ).count()
                                if current_count >= event.total_slots:
                                    continue
                            
                            # Assign number using counter
                            assigned_number = None
                            if event.type == 'raffle':
                                assigned_number = starting_number + new_participant_count
                                new_participant_count += 1
                            
                            # Create participant
                            participant = PublicEventParticipant(
                                event_id=event.id,
                                character_name=member['name'],
                                character_level=member.get('level'),
                                character_vocation=member.get('vocation'),
                                character_world=member.get('world', event.guild_world),
                                last_login=member.get('last_login'),
                                assigned_number=assigned_number,
                                is_auto_loaded=True
                            )
                            db.add(participant)
                    
                    db.commit()  # Commit all at once
                except Exception as e:
                    print(f"Error syncing participants: {e}")
    
    # Get participants from public_participants table
    if event.is_public:
        public_participants = db.query(PublicEventParticipant).filter(
            PublicEventParticipant.event_id == event.id,
            PublicEventParticipant.is_excluded == False,
            PublicEventParticipant.is_deleted == False,
        ).order_by(PublicEventParticipant.character_name).all()
        
        participants = [
            {
                'name': p.character_name,
                'level': p.character_level,
                'vocation': p.character_vocation,
                'number': p.assigned_number
            }
            for p in public_participants
        ]
        
        if event.is_drawn and event.winner_number:
            # Find winner by number - search in ALL participants (including excluded)
            winner = db.query(PublicEventParticipant).filter(
                PublicEventParticipant.event_id == event.id,
                PublicEventParticipant.assigned_number == event.winner_number
            ).first()
            if winner:
                winner_name = winner.character_name
    else:
        # Regular event with registered users
        participants = [
            {
                'name': p.user.username,
                'number': p.assigned_number
            }
            for p in event.participants
        ]
        
        if event.is_drawn and event.winner:
            winner_name = event.winner.username

    return {
        "is_drawn": event.is_drawn,
        "winner_number": event.winner_number,
        "winner_name": winner_name,
        "total_participants": len(participants),
        "participants": participants,
        "draw_date": event.draw_date.isoformat() if event.draw_date else None,
        "event_status": event.status
    }

@router.post("/{uuid}/raffle/draw")
async def auto_draw_raffle(
    uuid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """
    Draw raffle for public event via UUID (admin only).
    """
    event = db.query(Event).filter(Event.uuid == uuid).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
        
    if event.is_drawn:
        # Get winner info
        if event.is_public and event.public_participants:
            winner = next((p for p in event.public_participants if p.assigned_number == event.winner_number), None)
            winner_name = winner.character_name if winner else "Unknown"
        else:
            winner_name = event.winner.username if event.winner else "Unknown"
        
        return {
            "message": "Already drawn",
            "winner_number": event.winner_number,
            "winner_name": winner_name
        }
    
    # For public events, ensure participants are loaded
    if event.is_public:
        if event.participant_mode == 'guild_auto' and event.guild_name:
            # Final sync before drawing
            try:
                active_members = await get_active_guild_members(event.guild_name, event.active_days_limit)
                
                for member in active_members:
                    existing = db.query(PublicEventParticipant).filter(
                        PublicEventParticipant.event_id == event.id,
                        PublicEventParticipant.character_name == member['name']
                    ).first()
                    
                    if not existing:
                        # Check slots
                        if event.total_slots:
                            current_count = db.query(PublicEventParticipant).filter(
                                PublicEventParticipant.event_id == event.id
                            ).count()
                            if current_count >= event.total_slots:
                                continue
                        
# Assign number - use func.max
                        assigned_number = None
                        if event.type == 'raffle':
                            current_max = db.query(func.max(PublicEventParticipant.assigned_number)).filter(
                                PublicEventParticipant.event_id == event.id
                            ).scalar()
                            assigned_number = (current_max + 1) if current_max else 1
                        
                        participant = PublicEventParticipant(
                            event_id=event.id,
                            character_name=member['name'],
                            character_level=member.get('level'),
                            character_vocation=member.get('vocation'),
                            character_world=member.get('world', event.guild_world),
                            last_login=member.get('last_login'),
                            assigned_number=assigned_number,
                            is_auto_loaded=True
                        )
                        db.add(participant)
                
                db.commit()
                db.refresh(event)
            except Exception as e:
                print(f"Error syncing participants before draw: {e}")
        
        # Draw from public participants (exclude those marked as excluded)
        eligible_participants = [p for p in event.public_participants if not p.is_excluded]
        
        if not eligible_participants:
            raise HTTPException(status_code=400, detail="No eligible participants found")
        
        winner_participant = random.choice(eligible_participants)
        
        event.winner_number = winner_participant.assigned_number
        event.is_drawn = True
        event.status = 'completed'
        event.winner_id = None  # No user_id for external participants
        db.commit()
        
        return {
            "success": True,
            "winner_number": event.winner_number,
            "winner_name": winner_participant.character_name,
            "total_participants": len(event.public_participants)
        }
    else:
        # Private event - use registered participants
        if not event.participants:
            raise HTTPException(status_code=400, detail="No participants found")
        
        winner_participant = random.choice(event.participants)
        
        event.winner_id = winner_participant.user_id
        event.winner_number = winner_participant.assigned_number
        event.is_drawn = True
        event.status = 'completed'
        db.commit()
        
        return {
            "success": True,
            "winner_number": event.winner_number,
            "winner_name": event.winner.username,
            "total_participants": len(event.participants)
        }

@router.delete("/{event_id}/participants/{participant_id}", status_code=204)
async def delete_participant(
    event_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_manager_user)
):
    """Soft-delete a participant from a public event."""
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    
    if not event.is_public:
        raise HTTPException(status_code=400, detail="Can only delete participants from public events")
    
    participant = db.query(PublicEventParticipant).filter(
        PublicEventParticipant.id == participant_id,
        PublicEventParticipant.event_id == event_id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    participant.is_deleted = True
    participant.deleted_at = datetime.utcnow()
    participant.deleted_by_user_id = current_user.id
    participant.delete_reason = reason
    participant.is_excluded = True
    db.commit()
    
    return {"success": True}

@router.patch("/{event_id}/participants/{participant_id}/exclude")
async def exclude_participant(
    event_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user)
):
    """
    Mark a participant as excluded (admin only).
    Excluded participants won't be re-added during guild sync.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_management(current_user, event)
    
    if not event.is_public:
        raise HTTPException(status_code=400, detail="Can only exclude participants from public events")
    
    participant = db.query(PublicEventParticipant).filter(
        PublicEventParticipant.id == participant_id,
        PublicEventParticipant.event_id == event_id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    participant.is_excluded = True
    participant.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": f"{participant.character_name} marked as excluded"
    }
