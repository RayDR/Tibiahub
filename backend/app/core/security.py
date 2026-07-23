from datetime import UTC, datetime, timedelta
from typing import Any, Union
from jose import jwt
import bcrypt
import argon2
from app.core.config import settings

# Use both bcrypt (for existing passwords) and argon2 (for new passwords)
argon2_hasher = argon2.PasswordHasher()

ALGORITHM = "HS256"

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against stored hash.
    Supports both bcrypt (legacy) and argon2 (new) hashes.
    """
    # Check if it's a bcrypt hash (starts with $2a$, $2b$, or $2y$)
    if hashed_password.startswith(('$2a$', '$2b$', '$2y$')):
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False
    
    # Otherwise try argon2
    try:
        argon2_hasher.verify(hashed_password, plain_password)
        return True
    except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.InvalidHash):
        return False

def get_password_hash(password: str) -> str:
    """Hash password using argon2"""
    return argon2_hasher.hash(password)
