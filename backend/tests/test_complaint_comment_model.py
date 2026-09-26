"""Complaint comment model: created_at-only shape, defaults, and relationships."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.complaint import Complaint
from app.models.complaint_comment import ComplaintComment
from app.models.enums import ComplaintCategoryEnum
from app.repositories.complaint_comment import ComplaintCommentRepository


def make_complaint(db_session) -> Complaint:
    return Complaint(
        organization_id=uuid4(),
        property_id=uuid4(),
        resident_profile_id=uuid4(),
        title="Tap leaking",
        description="The bathroom tap drips constantly.",
        category=ComplaintCategoryEnum.PLUMBING,
    )


def test_table_name_is_complaint_comments() -> None:
    assert ComplaintComment.__tablename__ == "complaint_comments"


def test_is_internal_defaults_to_false(db_session) -> None:
    complaint = make_complaint(db_session)
    db_session.add(complaint)
    db_session.flush()

    comment = ComplaintComment(
        complaint_id=complaint.id, user_id=uuid4(), comment="Engineer visited."
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)

    assert comment.is_internal is False
    assert comment.created_at is not None


def test_is_internal_can_be_set_true(db_session) -> None:
    complaint = make_complaint(db_session)
    db_session.add(complaint)
    db_session.flush()

    comment = ComplaintComment(
        complaint_id=complaint.id,
        user_id=uuid4(),
        comment="Vendor quote is 4k, hold until month end.",
        is_internal=True,
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)

    assert comment.is_internal is True


def test_table_has_no_updated_at_and_no_organization_id(db_session) -> None:
    """Both omissions are deliberate (DATABASE.md §20 lists only `created_at`, and
    org scope comes from the parent complaint), so they are asserted rather than
    left to a reader's memory."""
    columns = {c.name for c in ComplaintComment.__table__.columns}
    assert "created_at" in columns
    assert "updated_at" not in columns
    assert "organization_id" not in columns


def test_complaint_back_populates_comments(db_session) -> None:
    complaint = make_complaint(db_session)
    db_session.add(complaint)
    db_session.flush()

    comment = ComplaintComment(
        complaint_id=complaint.id, user_id=uuid4(), comment="Plumber booked."
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(complaint)

    assert complaint.comments == [comment]
    assert comment.complaint is complaint


def test_user_back_populates_comments(db_session, create_user) -> None:
    from app.models.enums import RoleEnum

    user = create_user(email=f"author-{uuid4().hex[:8]}@example.com", role=RoleEnum.STAFF)
    complaint = make_complaint(db_session)
    db_session.add(complaint)
    db_session.flush()

    comment = ComplaintComment(
        complaint_id=complaint.id, user_id=user.id, comment="On it."
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(user)

    assert user.comments == [comment]
    assert comment.user is user


def test_deleting_a_complaint_does_not_silently_drop_comments(db_session) -> None:
    """Comments are immutable audit history, so the relationship carries no delete
    cascade. A complaint delete has to fail loudly rather than erase the thread."""
    complaint = make_complaint(db_session)
    db_session.add(complaint)
    db_session.flush()

    comment = ComplaintComment(
        complaint_id=complaint.id, user_id=uuid4(), comment="Plumber booked."
    )
    db_session.add(comment)
    db_session.commit()
    comment_id = comment.id

    db_session.delete(complaint)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.expire_all()
    assert ComplaintCommentRepository(db_session).get_by_id(comment_id) is not None
