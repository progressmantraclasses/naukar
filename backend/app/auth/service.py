"""
Auth Service — password hashing, JWT creation and decoding.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(payload: dict, expire_hours: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours or settings.JWT_EXPIRE_HOURS)
    to_encode = {**payload, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """/Raises JWTError if invalid/expired."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
