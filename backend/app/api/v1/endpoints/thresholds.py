from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.services.alerts import active_thresholds

router = APIRouter(prefix="/thresholds", tags=["thresholds"])


@router.get("")
def list_thresholds(db: DbSession, _user: CurrentUser):
    configured = active_thresholds(db)
    return [
        {"parameter": parameter, **details}
        for parameter, details in configured.provenance.items()
    ]
