"""Authentication, identity validation, and authorization helpers."""
import re
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:@-]{1,200}$")
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    user_id: str
    workspace_id: str


def _valid_id(value: str, fallback: str) -> str:
    return value if _ID_PATTERN.fullmatch(value or "") else fallback


async def get_identity(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Identity:
    if settings.AUTH_REQUIRED:
        if not credentials or not secrets.compare_digest(credentials.credentials, settings.AUTH_TOKEN):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        user_id = settings.AUTH_DEFAULT_USER_ID
    else:
        user_id = settings.AUTH_DEFAULT_USER_ID
    return Identity(user_id=_valid_id(user_id, "anonymous"), workspace_id=settings.AUTH_DEFAULT_WORKSPACE_ID)


def assert_owner(owner_id: str, identity: Identity):
    if owner_id != identity.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
