"""Pydantic request/response models. Every API payload is validated by these."""

from app.schemas.auth import RegisterRequest, RegisterResponse
from app.schemas.auth_me import AuthMeResponse
from app.schemas.bed import BedCreate, BedRead
from app.schemas.bed_api import BedUpdate
from app.schemas.building import BuildingCreate, BuildingRead
from app.schemas.building_api import BuildingUpdate
from app.schemas.floor import FloorCreate, FloorRead
from app.schemas.floor_api import FloorUpdate
from app.schemas.onboarding import OnboardingRequest, OnboardingResponse
from app.schemas.organization import OrganizationCreate, OrganizationRead
from app.schemas.organization_member import (
    OrganizationMemberCreate,
    OrganizationMemberRead,
)
from app.schemas.property import PropertyCreate, PropertyRead
from app.schemas.property_api import PropertyUpdate
from app.schemas.resident_profile import ResidentProfileCreate, ResidentProfileRead
from app.schemas.resident_profile_api import ResidentProfileUpdate
from app.schemas.room import RoomCreate, RoomRead
from app.schemas.room_api import RoomUpdate
from app.schemas.tenant_stay import TenantStayCreate, TenantStayRead
from app.schemas.tenant_stay_api import TenantStayUpdate

__all__ = [
    "AuthMeResponse",
    "BedCreate",
    "BedRead",
    "BedUpdate",
    "BuildingCreate",
    "BuildingRead",
    "BuildingUpdate",
    "FloorCreate",
    "FloorRead",
    "FloorUpdate",
    "OrganizationCreate",
    "OrganizationMemberCreate",
    "OrganizationMemberRead",
    "OrganizationRead",
    "OnboardingRequest",
    "OnboardingResponse",
    "PropertyCreate",
    "PropertyRead",
    "PropertyUpdate",
    "RegisterRequest",
    "RegisterResponse",
    "ResidentProfileCreate",
    "ResidentProfileRead",
    "ResidentProfileUpdate",
    "RoomCreate",
    "RoomRead",
    "RoomUpdate",
    "TenantStayCreate",
    "TenantStayRead",
    "TenantStayUpdate",
]