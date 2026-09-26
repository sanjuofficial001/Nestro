"""Complaint comment repository: per-complaint scoping, thread order, and the
`include_internal` seam."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.complaint import Complaint
from app.models.complaint_comment import ComplaintComment
from app.models.enums import ComplaintCategoryEnum
from app.repositories.complaint_comment import ComplaintCommentRepository


def make_complaint(db_session) -> Complaint:
    complaint = Complaint(
        organization_id=uuid4(),
        property_id=uuid4(),
        resident_profile_id=uuid4(),
        title="Tap leaking",
        description="The bathroom tap drips constantly.",
        category=ComplaintCategoryEnum.PLUMBING,
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)
    return complaint


def add_comment(
    db_session,
    complaint: Complaint,
    *,
    body: str = "Plumber booked.",
    is_internal: bool = False,
    created_at: datetime | None = None,
) -> ComplaintComment:
    """`created_at` is a server default with second resolution, so ordering tests
    stamp it explicitly."""
    comment = ComplaintComment(
        complaint_id=complaint.id,
        user_id=uuid4(),
        comment=body,
        is_internal=is_internal,
    )
    if created_at is not None:
        comment.created_at = created_at
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)
    return comment


def test_get_by_id_returns_none_for_unknown(db_session) -> None:
    assert ComplaintCommentRepository(db_session).get_by_id(uuid4()) is None


def test_get_by_id_returns_the_comment(db_session) -> None:
    complaint = make_complaint(db_session)
    comment = add_comment(db_session, complaint)

    assert ComplaintCommentRepository(db_session).get_by_id(comment.id) == comment


def test_create_maps_body_to_the_comment_column(db_session) -> None:
    """The API field is `body`; the column is `comment` (DATABASE.md §20)."""
    complaint = make_complaint(db_session)

    comment = ComplaintCommentRepository(db_session).create(
        complaint_id=complaint.id,
        user_id=uuid4(),
        body="Plumber booked.",
        is_internal=False,
    )

    assert comment.comment == "Plumber booked."
    assert not hasattr(comment, "body")
    assert comment.complaint_id == complaint.id


def test_create_defaults_and_persists_is_internal(db_session) -> None:
    complaint = make_complaint(db_session)

    comment = ComplaintCommentRepository(db_session).create(
        complaint_id=complaint.id, user_id=uuid4(), body="x", is_internal=True
    )

    db_session.expire_all()
    stored = ComplaintCommentRepository(db_session).get_by_id(comment.id)
    assert stored.is_internal is True


def test_list_returns_comments_for_that_complaint_only(db_session) -> None:
    mine = make_complaint(db_session)
    other = make_complaint(db_session)
    wanted = add_comment(db_session, mine, body="Mine")
    add_comment(db_session, other, body="Theirs")

    found = ComplaintCommentRepository(db_session).list_for_complaint(mine.id)
    assert found == [wanted]


def test_list_is_empty_for_a_complaint_with_no_comments(db_session) -> None:
    complaint = make_complaint(db_session)
    assert ComplaintCommentRepository(db_session).list_for_complaint(complaint.id) == []


def test_list_orders_oldest_first(db_session) -> None:
    complaint = make_complaint(db_session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    newest = add_comment(db_session, complaint, body="third", created_at=base + timedelta(hours=2))
    oldest = add_comment(db_session, complaint, body="first", created_at=base)
    middle = add_comment(db_session, complaint, body="second", created_at=base + timedelta(hours=1))

    found = ComplaintCommentRepository(db_session).list_for_complaint(complaint.id)
    assert [c.comment for c in found] == ["first", "second", "third"]
    assert found == [oldest, middle, newest]


def test_list_returns_internal_and_public(db_session) -> None:
    """Deferred-filter note: `is_internal` is persisted and returned, and nothing
    filters on it. Every caller of this endpoint is a staff-side role, so this
    documents current behaviour rather than a permanent visibility rule."""
    complaint = make_complaint(db_session)
    public = add_comment(db_session, complaint, body="public", is_internal=False)
    internal = add_comment(db_session, complaint, body="internal", is_internal=True)

    found = ComplaintCommentRepository(db_session).list_for_complaint(complaint.id)
    assert set(found) == {public, internal}
