from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, func, or_, select, text

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.core.security import create_access_token, hash_login_key, hash_password, verify_password
from app.models import AccessRequest, AuditLog, Clinic, LoginFailure, User
from app.schemas.resources import (
    AccessRequestCreate,
    AccessRequestDecision,
    AccessRequestPublic,
    ClinicPublic,
    Token,
    UserAdminPublic,
    UserCreate,
    UserPublic,
    UserStatusChange,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: Request, db: DbSession, form: OAuth2PasswordRequestForm = Depends()):
    now = datetime.now(UTC)
    identifier = form.username.strip().lower()
    identifier_hash = hash_login_key(f"identifier:{identifier}")
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
    user = db.scalar(select(User).where(or_(User.username == identifier, User.email == identifier)))
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


@router.get("/clinics", response_model=list[ClinicPublic])
def public_clinics(db: DbSession):
    return db.scalars(select(Clinic).where(Clinic.is_active.is_(True)).order_by(Clinic.name)).all()


@router.post("/users", response_model=UserPublic, status_code=201)
def create_user(payload: UserCreate, db: DbSession, admin: User = Depends(require_roles("admin"))):
    username = payload.username.strip().lower()
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(or_(User.username == username, User.email == email))):
        raise HTTPException(status_code=409, detail="Username or email already exists")
    clinic_id = payload.clinic_id
    if payload.role != "admin":
        clinic = db.get(Clinic, clinic_id) if clinic_id is not None else None
        if clinic is None or not clinic.is_active:
            raise HTTPException(status_code=422, detail="An active clinic is required for clinical staff")
    elif clinic_id is not None:
        raise HTTPException(status_code=422, detail="System administrators cannot be assigned to a clinic")
    user = User(
        username=username,
        email=email,
        role=payload.role,
        clinic_id=clinic_id,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    db.add(AuditLog(user_id=admin.id, action="create_user", resource_type="user", resource_id=user.id))
    db.commit()
    db.refresh(user)
    return user


@router.post("/request-access", status_code=202, response_model=AccessRequestPublic)
def request_access(payload: AccessRequestCreate, db: DbSession, request: Request):
    clinic = db.get(Clinic, payload.clinic_id)
    if clinic is None or not clinic.is_active:
        raise HTTPException(status_code=422, detail="Choose an active clinic")
    username = payload.username.strip().lower()
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(or_(User.username == username, User.email == email))):
        raise HTTPException(status_code=409, detail="Username or email already exists")
    if db.scalar(select(AccessRequest.id).where(
        AccessRequest.status == "pending",
        or_(AccessRequest.username == username, AccessRequest.email == email),
    )):
        raise HTTPException(status_code=409, detail="An access request for this username or email is already pending")
    item = AccessRequest(
        username=username,
        email=email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        clinic_id=payload.clinic_id,
    )
    db.add(item)
    db.flush()
    record_audit(db, action="request_access", resource_type="access_request", resource_id=item.id,
                 details={"clinic_id": item.clinic_id, "role": item.role})
    db.commit()
    db.refresh(item)
    return item


@router.get("/users", response_model=list[UserAdminPublic])
def list_users(
    db: DbSession,
    response: Response,
    admin: User = Depends(require_roles("admin")),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    total = db.scalar(select(func.count(User.id))) or 0
    users = db.scalars(select(User).order_by(User.username).offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(users)) if offset + len(users) < total else ""
    return [UserAdminPublic.model_validate({**UserPublic.model_validate(user).model_dump(), "status": "active" if user.is_active else "disabled"}) for user in users]


@router.get("/access-requests", response_model=list[AccessRequestPublic])
def list_access_requests(
    db: DbSession,
    response: Response,
    admin: User = Depends(require_roles("admin")),
    status_filter: str | None = Query(default="pending", alias="status", pattern="^(pending|approved|rejected)$"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = select(AccessRequest).order_by(AccessRequest.created_at.desc(), AccessRequest.id.desc())
    if status_filter:
        query = query.where(AccessRequest.status == status_filter)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = db.scalars(query.offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(items)) if offset + len(items) < total else ""
    return items


@router.patch("/access-requests/{request_id}", response_model=AccessRequestPublic)
def decide_access_request(
    request_id: int,
    payload: AccessRequestDecision,
    db: DbSession,
    admin: User = Depends(require_roles("admin")),
):
    item = db.scalar(select(AccessRequest).where(AccessRequest.id == request_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Access request not found")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail="Access request has already been reviewed")
    if payload.action == "approve":
        if db.scalar(select(User.id).where(or_(User.username == item.username, User.email == item.email))):
            raise HTTPException(status_code=409, detail="A user with this username or email already exists")
        db.add(User(username=item.username, email=item.email, hashed_password=item.hashed_password,
                    role=item.role, clinic_id=item.clinic_id, is_active=True))
        item.status = "approved"
    else:
        item.status = "rejected"
    item.reviewed_by_user_id = admin.id
    item.reviewed_at = datetime.now(UTC)
    record_audit(db, user_id=admin.id, action=f"{payload.action}_access_request", resource_type="access_request", resource_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/users/{user_id}", response_model=UserAdminPublic)
def update_user_status(
    user_id: int,
    payload: UserStatusChange,
    db: DbSession,
    admin: User = Depends(require_roles("admin")),
):
    action = payload.action
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin" or user.id == admin.id:
        raise HTTPException(status_code=409, detail="System administrator accounts cannot be changed here")
    user.is_active = action == "enable"
    record_audit(db, user_id=admin.id, action=f"{action}_user", resource_type="user", resource_id=user.id)
    db.commit()
    db.refresh(user)
    return UserAdminPublic.model_validate({**UserPublic.model_validate(user).model_dump(), "status": "active" if user.is_active else "disabled"})
