import logging
from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.core import security, config
from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.schemas.auth import UserCreate, UserResponse, Token, TokenData
from app.services.tibia_validation_service import TibiaValidationService
from app.services.tibia_sync_service import try_sync_user_character_snapshot
from app.core.permissions import is_global_admin, is_guild_leader

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
logger = logging.getLogger(__name__)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_admin_user(current_user: User = Depends(get_current_active_user)):
    if not is_global_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )
    return current_user


def get_current_manager_user(current_user: User = Depends(get_current_active_user)):
    if not (is_global_admin(current_user) or is_guild_leader(current_user)):
        raise HTTPException(
            status_code=403,
            detail="Manager privileges required",
        )
    return current_user

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    login_input = (form_data.username or "").strip()
    logger.info("login_attempt login=%s", login_input)

    # Try to find user by username first (case-insensitive for resilience)
    user = db.query(User).filter(User.username.ilike(login_input)).first()

    # If still not found by username, try email
    if not user and "@" in login_input:
        user = db.query(User).filter(User.email.ilike(login_input)).first()
    
    # If not found by username, try to find by character name
    if not user:
        user_char = db.query(UserCharacter).filter(UserCharacter.character_name.ilike(login_input)).first()
        if user_char:
            user = user_char.user

    logger.info("login_user_found login=%s found=%s", login_input, bool(user))
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username/email or password")

    if not security.verify_password(form_data.password, user.hashed_password):
        logger.info("login_password_valid username=%s valid=false", user.username)
        raise HTTPException(status_code=400, detail="Invalid username/email or password")

    logger.info("login_password_valid username=%s valid=true", user.username)

    if not user.is_active:
        logger.info("login_user_inactive username=%s", user.username)
        raise HTTPException(status_code=400, detail="Inactive user")

    logger.info(
        "login_user_state username=%s is_active=%s is_superuser=%s guild_rank=%s",
        user.username,
        user.is_active,
        user.is_superuser,
        user.guild_rank,
    )
    
    access_token_expires = timedelta(minutes=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(user.username, expires_delta=access_token_expires),
        "token_type": "bearer",
    }

@router.post("/register", response_model=UserResponse)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    # Check if username already exists
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(status_code=400, detail="The user with this username already exists in the system.")
    
    # Check if email already exists (if provided)
    if user_in.email:
        existing_email = db.query(User).filter(User.email == user_in.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="The email is already registered.")
    
    # Tibia character validation
    tibia_character_data = None
    if user_in.tibia_character_name and config.settings.TIBIA_VALIDATION_ENABLED:
        # Check if character already linked
        existing_char = db.query(UserCharacter).filter(
            UserCharacter.character_name == user_in.tibia_character_name
        ).first()
        if existing_char:
            raise HTTPException(
                status_code=400, 
                detail="This Tibia character is already linked to another account."
            )
        
        # Validate character using the validation service
        is_valid, char_data, error_msg = TibiaValidationService.validate_character(
            user_in.tibia_character_name,
            strict=config.settings.TIBIA_VALIDATION_STRICT
        )
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg or "Could not validate Tibia character")
        
        # Store character data if available
        if char_data:
            tibia_character_data = char_data

    # Create user
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        guild_rank="Member",
        tibia_character_name=tibia_character_data.get("name") if tibia_character_data else user_in.tibia_character_name,
        level=tibia_character_data.get("level") if tibia_character_data else None,
        vocation=tibia_character_data.get("vocation") if tibia_character_data else None,
        world_name=tibia_character_data.get("world") if tibia_character_data else None,
        residence=tibia_character_data.get("residence") if tibia_character_data else None,
        tibia_status="validated" if tibia_character_data else None,
        join_date=datetime.utcnow(),
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create UserCharacter link if character name provided
    if user_in.tibia_character_name:
        user_char = UserCharacter(
            user_id=user.id,
            character_name=tibia_character_data["name"] if tibia_character_data else user_in.tibia_character_name,
            level=tibia_character_data.get("level") if tibia_character_data else None,
            vocation=tibia_character_data.get("vocation") if tibia_character_data else None,
            world_name=tibia_character_data.get("world") if tibia_character_data else None,
            residence=tibia_character_data.get("residence") if tibia_character_data else None,
        )
        db.add(user_char)
        db.commit()
        db.refresh(user_char)

    if user.tibia_character_name:
        def _sync_character():
            try:
                import asyncio
                asyncio.run(try_sync_user_character_snapshot(db, user))
            except Exception as exc:
                logger.warning("register_character_sync_skipped username=%s error=%s", user.username, exc)
        
        background_tasks.add_task(_sync_character)
    
    return user

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
