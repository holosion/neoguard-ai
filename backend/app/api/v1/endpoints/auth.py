from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, func, or_, select, text

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.core.security import create_access_token, hash_login_key, hash_password, verify_password
from app.models import AuditLog, LoginFailure, User
from app.schemas.resources import Token, UserCreate, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: Request, db: DbSession, form: OAuth2PasswordRequestForm = Depends()):
    now = datetime.now(UTC)
    identifier_hash = hash_login_key(f"identifier:{form.username}")
    source_hash = hash_login_key(f"source:{request.client.host if request.client else 'unknown'}")
    # Serialize attempts against both buckets so simultaneous requests cannot bypass limits.
    for lock_key in sorted((identifier_hash, source_hash)):
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": lock_key})
    db.execute(delete(LoginFailure).where(LoginFailure.created_at < now - timedelta(days=1)))
    identifier_count = db.scalar(
        select(func.count(LoginFailure.id)).where(
            LoginFailure.identifier_hash == identifier_hash,
            LoginFailure.created_at >= now - timedelta(seconds=settings.login_identifier_window_seconds),
        )
    ) or 0
    source_count = db.scalar(
        select(func.count(LoginFailure.id)).where(
            LoginFailure.source_hash == source_hash,
            LoginFailure.created_at >= now - timedelta(seconds=settings.login_source_window_seconds),
        )
    ) or 0
    if identifier_count >= settings.login_identifier_max_attempts or source_count >= settings.login_source_max_attempts:
        db.rollback()
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": "900"},
        )
    user = db.scalar(select(User).where(or_(User.username == form.username, User.email == form.username)))
    if user is None or not user.is_active or not verify_password(form.password, user.hashed_password):
        db.add(LoginFailure(identifier_hash=identifier_hash, source_hash=source_hash))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username/email or password")
    db.execute(delete(LoginFailure).where(LoginFailure.identifier_hash == identifier_hash))
    db.add(AuditLog(user_id=user.id, action="login", resource_type="user", resource_id=user.id))
    db.commit()
    return Token(access_token=create_access_token(subject=str(user.id), role=user.role))


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser):
    return user


@router.post("/users", response_model=UserPublic, status_code=201)
def create_user(payload: UserCreate, db: DbSession, admin: User = Depends(require_roles("admin"))):
    if db.scalar(select(User).where(or_(User.username == payload.username, User.email == payload.email))):
        raise HTTPException(status_code=409, detail="Username or email already exists")
    user = User(
        username=payload.username,
        email=str(payload.email),
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    db.add(AuditLog(user_id=admin.id, action="create_user", resource_type="user", resource_id=user.id))
    db.commit()
    db.refresh(user)
    return user
