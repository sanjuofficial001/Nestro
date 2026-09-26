"""Pydantic models for complaint comments.

The field is `body` on both the request and the response because that is what
API_SPEC endpoint 53 puts on the wire, so a client uses one name in both
directions. The database column is `comment` (DATABASE.md §20); the repository
maps between the two, so the naming difference never reaches the API.

`complaint_id` is absent from `ComplaintCommentCreate` on purpose: the complaint
comes from the path (`/complaints/{complaint_id}/comments`), so a body that also
carries it would be a second, spoofable source for the same value. `extra=
"forbid"` turns that into a 422 rather than a silent no-op.

Comments are immutable — there is no update schema and no `updated_at` — so
there is nothing here that can edit an existing comment.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.complaint import _strip_text

COMMENT_MAX_LENGTH = 2000


class ComplaintCommentBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=COMMENT_MAX_LENGTH)
    is_internal: bool = False

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        return _strip_text(value)


class ComplaintCommentCreate(ComplaintCommentBase):
    """Payload for adding a comment to a complaint thread."""


class ComplaintCommentRead(ComplaintCommentBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    # Validated from the ORM attribute `comment`, serialized back out as `body`:
    # only a validation alias is set, and FastAPI falls back to the field name
    # when no serialization alias exists.
    body: str = Field(validation_alias="comment")
    id: UUID
    complaint_id: UUID
    user_id: UUID
    created_at: datetime
