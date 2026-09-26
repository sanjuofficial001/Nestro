"""Organization-scoped tenant stay endpoints.

Authorization is org-scoped through `TenantStayService`: OWNER/MANAGER may write,
any member may read, and the platform-wide SUPER_ADMIN role bypasses. Only
`organization_id` is taken from the caller; a stay's organization always derives
from the row itself. Bed, resident, property, and start date are immutable — a
stay records who/where/when occupancy began, so transfers and resident
reassignment are not part of this surface.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.enums import TenantStayStatusEnum
from app.models.user import User
from app.schemas.tenant_stay import TenantStayCreate, TenantStayRead
from app.schemas.tenant_stay_api import TenantStayUpdate
from app.services.tenant_stay_service import TenantStayService

router = APIRouter(prefix="/tenant-stays", tags=["tenant-stays"])


@router.post("", response_model=TenantStayRead, status_code=201)
def create_tenant_stay(
    payload: TenantStayCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantStayRead:
    try:
        stay = TenantStayService(db).create_tenant_stay(current_user, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return TenantStayRead.model_validate(stay)


@router.get("", response_model=list[TenantStayRead])
def list_tenant_stays(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    resident_profile_id: UUID | None = None,
    bed_id: UUID | None = None,
    status: TenantStayStatusEnum | None = None,
) -> list[TenantStayRead]:
    try:
        stays = TenantStayService(db).list_tenant_stays(
            current_user, organization_id, resident_profile_id, bed_id, status
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return [TenantStayRead.model_validate(stay) for stay in stays]


@router.get("/{stay_id}", response_model=TenantStayRead)
def get_tenant_stay(
    stay_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantStayRead:
    try:
        stay = TenantStayService(db).get_tenant_stay(current_user, stay_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return TenantStayRead.model_validate(stay)


@router.patch("/{stay_id}", response_model=TenantStayRead)
def update_tenant_stay(
    stay_id: UUID,
    payload: TenantStayUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantStayRead:
    try:
        stay = TenantStayService(db).update_tenant_stay(
            current_user, stay_id, payload
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return TenantStayRead.model_validate(stay)
