"""Organization-scoped complaint CRUD endpoints.

Authorization is org-scoped through `ComplaintService`: OWNER/MANAGER may write,
any member may read, and the platform-wide SUPER_ADMIN role bypasses. Only
`organization_id` is taken from the caller; a complaint's organization always
derives from the row itself.

Resident-facing complaint creation, complaint comments, and the reopen/audit
workflow are separate future work (API_SPEC §10, DATABASE.md §20).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.enums import ComplaintPriorityEnum, ComplaintStatusEnum
from app.models.user import User
from app.schemas.complaint import ComplaintCreate, ComplaintRead
from app.schemas.complaint_api import ComplaintUpdate
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.post("", response_model=ComplaintRead, status_code=201)
def create_complaint(
    payload: ComplaintCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ComplaintRead:
    try:
        complaint = ComplaintService(db).create_complaint(current_user, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ComplaintRead.model_validate(complaint)


@router.get("", response_model=list[ComplaintRead])
def list_complaints(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    status: ComplaintStatusEnum | None = None,
    priority: ComplaintPriorityEnum | None = None,
    resident_profile_id: UUID | None = None,
) -> list[ComplaintRead]:
    try:
        complaints = ComplaintService(db).list_complaints(
            current_user, organization_id, status, priority, resident_profile_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return [ComplaintRead.model_validate(c) for c in complaints]


@router.get("/{complaint_id}", response_model=ComplaintRead)
def get_complaint(
    complaint_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ComplaintRead:
    try:
        complaint = ComplaintService(db).get_complaint(current_user, complaint_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ComplaintRead.model_validate(complaint)


@router.patch("/{complaint_id}", response_model=ComplaintRead)
def update_complaint(
    complaint_id: UUID,
    payload: ComplaintUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ComplaintRead:
    try:
        complaint = ComplaintService(db).update_complaint(
            current_user, complaint_id, payload
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ComplaintRead.model_validate(complaint)
