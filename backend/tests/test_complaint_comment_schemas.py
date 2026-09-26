"""Complaint comment schema validation: bounds, stripping, and what the wire accepts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.complaint_comment import ComplaintComment
from app.schemas.complaint_comment import (
    ComplaintCommentCreate,
    ComplaintCommentRead,
)


def test_is_internal_defaults_to_false() -> None:
    assert ComplaintCommentCreate(body="Plumber booked.").is_internal is False


def test_is_internal_accepts_true() -> None:
    assert ComplaintCommentCreate(body="x", is_internal=True).is_internal is True


def test_body_strips_surrounding_whitespace() -> None:
    assert ComplaintCommentCreate(body="  Plumber booked.  ").body == "Plumber booked."


def test_body_rejects_over_2000_chars() -> None:
    with pytest.raises(ValidationError):
        ComplaintCommentCreate(body="x" * 2001)


def test_body_accepts_exactly_2000_chars() -> None:
    assert len(ComplaintCommentCreate(body="x" * 2000).body) == 2000


def test_blank_body_after_strip_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ComplaintCommentCreate(body="   ")


def test_create_rejects_complaint_id_in_the_body() -> None:
    """The complaint comes from the path; accepting it in the body would be a second,
    spoofable source for the same value."""
    with pytest.raises(ValidationError):
        ComplaintCommentCreate(body="x", complaint_id=uuid4())


def test_create_rejects_user_id_in_the_body() -> None:
    with pytest.raises(ValidationError):
        ComplaintCommentCreate(body="x", user_id=uuid4())


def test_create_rejects_updated_at() -> None:
    with pytest.raises(ValidationError):
        ComplaintCommentCreate(body="x", updated_at=datetime.now(UTC))


def test_create_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ComplaintCommentCreate(body="x", moderator_id=str(uuid4()))


def test_read_serializes_the_body_field() -> None:
    """The API field is `body` in both directions, even though the column is `comment`."""
    complaint_id = uuid4()
    comment = ComplaintComment(
        id=uuid4(),
        complaint_id=complaint_id,
        user_id=uuid4(),
        comment="Plumber booked.",
        is_internal=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    read = ComplaintCommentRead.model_validate(comment)
    assert read.body == "Plumber booked."
    assert read.is_internal is True
    assert read.complaint_id == complaint_id

    dumped = read.model_dump()
    assert "body" in dumped
    assert "comment" not in dumped
