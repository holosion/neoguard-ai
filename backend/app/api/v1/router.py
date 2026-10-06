from fastapi import APIRouter

from app.api.v1.endpoints import admin, alerts, auth, devices, patients, sessions

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(devices.router)
api_router.include_router(sessions.router)
api_router.include_router(alerts.router)
api_router.include_router(admin.router)
