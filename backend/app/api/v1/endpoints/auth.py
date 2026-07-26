import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError, TimeoutError as SATimeoutError
from jose import jwt, JWTError

from app.core import security, config
from app.db.database import get_db
from app.models.user import User
from app.models.user_character import UserCharacter
from app.schemas.auth import UserCreate, UserResponse, Token, TokenData
from app.core.permissions import is_global_admin, is_guild_leader
from app.services.character_ownership_service import normalize_character_name

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
        payload = jwt.decode(token, config.settings.secret_key, algorithms=[security.ALGORITHM])
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
        raise HTTPException(status_code=403, detail="Your account is inactive. Please contact an administrator.")
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
    start = time.perf_counter()
    login_input = (form_data.username or "").strip()
    normalized_login = login_input.casefold()
    logger.info("login_request_started")

    try:
        lookup_start = time.perf_counter()

        # Try username first (case-insensitive for resilience).
        user = db.query(User).filter(func.lower(User.username) == normalized_login).first()

        # If still not found by username, try email.
        if not user and "@" in login_input:
            user = db.query(User).filter(func.lower(User.email) == normalized_login).first()

        # If not found by username/email, try linked character name.
        if not user:
            user_char = db.query(UserCharacter).filter(
                UserCharacter.normalized_name == normalize_character_name(login_input),
                UserCharacter.ownership_status == "verified",
            ).first()
            if user_char:
                user = user_char.user

        lookup_ms = int((time.perf_counter() - lookup_start) * 1000)
        logger.info("login_user_lookup_done found=%s duration_ms=%s", bool(user), lookup_ms)

        if not user:
            total_ms = int((time.perf_counter() - start) * 1000)
            logger.warning("login_failed category=invalid_credentials status=401 total_ms=%s", total_ms)
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        verify_start = time.perf_counter()
        password_valid = security.verify_password(form_data.password, user.hashed_password)
        verify_ms = int((time.perf_counter() - verify_start) * 1000)
        logger.info("login_password_verify_done valid=%s duration_ms=%s", password_valid, verify_ms)

        if not password_valid:
            total_ms = int((time.perf_counter() - start) * 1000)
            logger.warning("login_failed category=invalid_credentials status=401 total_ms=%s", total_ms)
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        if not user.is_active:
            total_ms = int((time.perf_counter() - start) * 1000)
            logger.warning("login_failed category=inactive_user status=403 total_ms=%s", total_ms)
            raise HTTPException(status_code=403, detail="Your account is inactive. Please contact an administrator.")

        # Application authentication is tracked separately from Tibia character
        # activity (`last_login_at`), which is populated by TibiaData sync.
        user.last_app_login_at = datetime.now(UTC)
        db.commit()

        token_start = time.perf_counter()
        access_token_expires = timedelta(minutes=config.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token = security.create_access_token(user.username, expires_delta=access_token_expires)
        token_ms = int((time.perf_counter() - token_start) * 1000)

        total_ms = int((time.perf_counter() - start) * 1000)
        logger.warning(
            "login_success lookup_ms=%s verify_ms=%s token_ms=%s total_ms=%s",
            lookup_ms,
            verify_ms,
            token_ms,
            total_ms,
        )

        return {
            "access_token": token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except SATimeoutError as exc:
        db.rollback()
        total_ms = int((time.perf_counter() - start) * 1000)
        logger.error("login_failed category=database_timeout status=503 total_ms=%s error=%s", total_ms, exc)
        raise HTTPException(status_code=503, detail="The server is temporarily unavailable. Please try again later.") from exc
    except OperationalError as exc:
        db.rollback()
        total_ms = int((time.perf_counter() - start) * 1000)
        logger.error("login_failed category=database_error status=503 total_ms=%s error=%s", total_ms, exc)
        raise HTTPException(status_code=503, detail="The server is temporarily unavailable. Please try again later.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        total_ms = int((time.perf_counter() - start) * 1000)
        logger.error("login_failed category=database_error status=503 total_ms=%s error=%s", total_ms, exc)
        raise HTTPException(status_code=503, detail="The server is temporarily unavailable. Please try again later.") from exc
    except TimeoutError as exc:
        total_ms = int((time.perf_counter() - start) * 1000)
        logger.error("login_failed category=server_timeout status=503 total_ms=%s error=%s", total_ms, exc)
        raise HTTPException(status_code=503, detail="The server is temporarily unavailable. Please try again later.") from exc
    except Exception as exc:
        total_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("login_failed category=unexpected_error status=500 total_ms=%s error=%s", total_ms, exc)
        raise HTTPException(status_code=500, detail="The server is temporarily unavailable. Please try again later.") from exc

@router.post("/register", response_model=UserResponse)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    # Check if username already exists
    normalized_username = user_in.username.casefold()
    user = db.query(User).filter(func.lower(User.username) == normalized_username).first()
    if user:
        raise HTTPException(status_code=400, detail="The user with this username already exists in the system.")
    
    # Check if email already exists (if provided)
    if user_in.email:
        normalized_email = str(user_in.email).casefold()
        existing_email = db.query(User).filter(func.lower(User.email) == normalized_email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="The email is already registered.")
    
    # Existence is not ownership. Character names supplied during registration
    # are never linked; the authenticated public-comment challenge owns that job.
    user = User(
        username=user_in.username,
        email=str(user_in.email).casefold() if user_in.email else None,
        hashed_password=security.get_password_hash(user_in.password),
        guild_rank="Unranked",
        tibia_character_name=None,
        tibia_status="ownership_unverified" if user_in.tibia_character_name else None,
        join_date=datetime.now(UTC),
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    db.flush()
    raw_token = None
    if user.email:
        from datetime import timedelta
        from app.api.v1.endpoints.email_verification import queue_verification_email
        from app.services.auth_token_service import AuthTokenService, EMAIL_VERIFICATION
        raw_token = AuthTokenService.issue(
            db, user=user, purpose=EMAIL_VERIFICATION,
            ttl=timedelta(hours=config.settings.EMAIL_VERIFICATION_TTL_HOURS),
        )
    db.commit()
    db.refresh(user)
    if raw_token:
        queue_verification_email(background_tasks, user=user, raw_token=raw_token, locale=user_in.locale)
    
    return user

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
