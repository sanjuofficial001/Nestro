"""Pydantic request/response models. Every API payload is validated by these."""

from app.schemas.bed import BedCreate, BedRead
from app.schemas.building import BuildingCreate, BuildingRead
from app.schemas.floor import FloorCreate, FloorRead
from app.schemas.organization import OrganizationCreate, OrganizationRead
from app.schemas.organization_member import (
    OrganizationMemberCreate,
    OrganizationMemberRead,
)
from app.schemas.property import PropertyCreate, PropertyRead
from app.schemas.resident_profile import ResidentProfileCreate, ResidentProfileRead
from app.schemas.room import RoomCreate, RoomRead
from app.schemas.tenant_stay import TenantStayCreate, TenantStayRead

__all__ = [
    "BedCreate",
    "BedRead",
    "BuildingCreate",
    "BuildingRead",
    "FloorCreate",
    "FloorRead",
    "OrganizationCreate",
    "OrganizationMemberCreate",
    "OrganizationMemberRead",
    "OrganizationRead",
    "PropertyCreate",
    "PropertyRead",
    "ResidentProfileCreate",
    "ResidentProfileRead",
    "RoomCreate",
    "RoomRead",
    "TenantStayCreate",
    "TenantStayRead",
]