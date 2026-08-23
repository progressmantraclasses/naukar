"""Authentication, identity validation, and authorization helpers."""
import re
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.config import settings

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:@-]{1,200}$")
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    user_id: str
    workspace_id: str
    email: str = ""
    role: str = "user"


def _valid_id(value: str, fallback: str) -> str:
    return value if _ID_PATTERN.fullmatch(value or "") else fallback


async def get_identity(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Identity:
    """
    Decode JWT and return Identity.
    When AUTH_REQUIRED=False, returns anonymous identity (dev mode only).
    """
    if not settings.AUTH_REQUIRED:
        return Identity(
            user_id=settings.AUTH_DEFAULT_USER_ID,
            workspace_id=settings.AUTH_DEFAULT_WORKSPACE_ID,
            email="dev@local",
            role="user",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from app.auth.service import decode_access_token
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub", "")
    workspace_id = payload.get("workspace_id", "")
    email = payload.get("email", "")
    role = payload.get("role", "user")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token.",
        )

    return Identity(
        user_id=_valid_id(user_id, "anonymous"),
        workspace_id=_valid_id(workspace_id, "default"),
        email=email,
        role=role,
    )


async def require_admin(identity: Identity = Depends(get_identity)) -> Identity:
    """Require admin role."""
    if identity.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return identity


def assert_owner(owner_id: str, identity: Identity):
    """Raises 404 (not 403) to prevent resource enumeration."""
    if owner_id != identity.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")

