from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AuditLog, User
from app.schemas.resources import Token, UserCreate, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(db: DbSession, form: OAuth2PasswordRequestForm = Depends()):
    user = db.scalar(select(User).where(or_(User.username == form.username, User.email == form.username)))
    if user is None or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username/email or password")
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
