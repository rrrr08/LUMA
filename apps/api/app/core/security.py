import secrets
import hashlib
from typing import Tuple, Optional, Any, Union
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[str]:
    """Decodes a JWT access token and returns the subject if valid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


API_KEY_PREFIX = "sk_live_"

def generate_api_key() -> Tuple[str, str]:
    """
    Generates a secure API key.
    Returns:
        A tuple of (raw_key, hashed_key)
        - raw_key: String to display to the user once (e.g., 'sk_live_abcdef123...')
        - hashed_key: Hex string to store in the database
    """
    token = secrets.token_urlsafe(32)
    raw_key = f"{API_KEY_PREFIX}{token}"
    hashed_key = hash_api_key(raw_key)
    return raw_key, hashed_key

def hash_api_key(key: str) -> str:
    """
    Hashes an API key securely using SHA256.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Securely compares a provided API key against a stored hash using constant-time comparison.
    """
    provided_hash = hash_api_key(provided_key)
    return secrets.compare_digest(provided_hash, stored_hash)
