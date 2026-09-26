"""Aggregates all v1 routes into a single router included by the app entrypoint."""

from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.beds import router as beds_router
from app.api.v1.routes.buildings import router as buildings_router
from app.api.v1.routes.floors import router as floors_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.properties import router as properties_router
from app.api.v1.routes.resident_profiles import router as resident_profiles_router
from app.api.v1.routes.rooms import router as rooms_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(health_router)
api_router.include_router(properties_router)
api_router.include_router(buildings_router)
api_router.include_router(floors_router)
api_router.include_router(rooms_router)
api_router.include_router(beds_router)
api_router.include_router(resident_profiles_router)