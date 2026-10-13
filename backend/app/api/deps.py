from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, hash_device_secret
from app.models import Device, DeviceCredential, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DbSession = Annotated[Session, Depends(get_db)]


def _load_user(token: str, db: Session, *, allow_password_change: bool) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", ""))
        token_version = int(payload.get("ver", 0))
    except (ValueError, TypeError):
        raise credentials_error
    user = db.get(User, user_id)
    if user is None or not user.is_active or token_version != user.token_version:
        raise credentials_error
    if user.must_change_password and not allow_password_change:
        raise HTTPException(status_code=403, detail="Password change required before accessing this resource")
    if payload.get("pwd_change_only") and not allow_password_change:
        raise HTTPException(status_code=403, detail="This temporary session can only change its password")
    return user


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    return _load_user(token, db, allow_password_change=False)


def get_password_change_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    return _load_user(token, db, allow_password_change=True)


CurrentUser = Annotated[User, Depends(get_current_user)]
PasswordChangeUser = Annotated[User, Depends(get_password_change_user)]


def require_roles(*roles: str):
    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


def get_authenticated_device(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> Device:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Device bearer token required")
    secret = authorization.removeprefix("Bearer ").strip()
    credential = db.scalar(
        select(DeviceCredential).where(
            DeviceCredential.secret_hash == hash_device_secret(secret),
            DeviceCredential.is_active.is_(True),
        )
    )
    if credential is None:
        raise HTTPException(status_code=401, detail="Invalid device credentials")
    device = db.get(Device, credential.device_id)
    if device is None or device.status != "active":
        raise HTTPException(status_code=403, detail="Device is not active")
    return device


AuthenticatedDevice = Annotated[Device, Depends(get_authenticated_device)]
