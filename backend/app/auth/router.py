"""
Auth Router - /auth/register, /auth/login, /auth/me
"""
import re
import uuid
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import create_access_token, hash_password, verify_password
from app.core.database import get_db
from app.core.security import get_identity, Identity
from app.db.models import User

log = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])

_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,128}$")

# ── Schemas ────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if not _PASSWORD_RE.match(v):
            raise ValueError("Password must be 8-128 chars with at least one letter and one digit.")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    workspace_id: str
    role: str

class UserResponse(BaseModel):
    user_id: str
    email: str
    workspace_id: str
    role: str

# ── Rate limit (in-memory sliding window) ─────────────────────────────────
_login_attempts: dict = {}

def _check_login_rate(ip: str):
    now = time.time()
    window, limit = 60, 5
    _login_attempts.setdefault(ip, [])
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < window]
    if len(_login_attempts[ip]) >= limit:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in a minute.", headers={"Retry-After": "60"})
    _login_attempts[ip].append(now)

# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email_lower = body.email.lower().strip()
    existing = await db.scalar(select(User).where(User.email == email_lower))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")
    user = User(
        email=email_lower,
        hashed_password=hash_password(body.password),
        workspace_id=str(uuid.uuid4()),
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": user.id, "email": user.email, "workspace_id": user.workspace_id, "role": user.role})
    log.info("user_registered", user_id=user.id, email=email_lower)
    return TokenResponse(access_token=token, user_id=user.id, email=user.email, workspace_id=user.workspace_id, role=user.role)

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate(client_ip)
    email_lower = body.email.lower().strip()
    user = await db.scalar(select(User).where(User.email == email_lower))
    if not user or not user.is_active or not verify_password(body.password, user.hashed_password):
        log.warning("login_failed", ip=client_ip, email=email_lower)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    token = create_access_token({"sub": user.id, "email": user.email, "workspace_id": user.workspace_id, "role": user.role})
    log.info("user_logged_in", user_id=user.id, email=email_lower)
    return TokenResponse(access_token=token, user_id=user.id, email=user.email, workspace_id=user.workspace_id, role=user.role)

@router.get("/me", response_model=UserResponse)
async def get_me(identity: Identity = Depends(get_identity)):
    return UserResponse(user_id=identity.user_id, email=identity.email, workspace_id=identity.workspace_id, role=identity.role)
