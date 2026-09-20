"""Tests for the tenant stay repository on SQLite, verifying scoping, ordering,
and the active-stay-per-bed uniqueness guarantee."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.bed import Bed
from app.models.building import Building
from app.models.enums import (
    BedStatusEnum,
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
    RoomTypeEnum,
    TenantStayStatusEnum,
)
from app.models.floor import Floor
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.property import Property
from app.models.resident_profile import ResidentProfile
from app.models.room import Room
from app.models.tenant_stay import TenantStay
from app.models.user import User
from app.repositories.bed import BedRepository
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.room import RoomRepository
from app.repositories.tenant_stay import TenantStayRepository
from app.repositories.user import UserRepository
from app.schemas.bed import BedCreate
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.room import RoomCreate
from app.schemas.tenant_stay import TenantStayCreate
from app.schemas.user import UserCreate


def create_org(repo: OrganizationRepository, *, slug: str) -> Organization:
    return repo.create(OrganizationCreate(name=slug.title(), slug=slug))


def create_user(repo: UserRepository, *, email: str) -> User:
    return repo.create(
        UserCreate(email=email, phone=None, full_name="Test User", role=RoleEnum.TENANT)
    )


def create_member(
    repo: OrganizationMemberRepository, org: Organization, user: User
) -> OrganizationMember:
    return repo.create(
        OrganizationMemberCreate(
            organization_id=org.id,
            user_id=user.id,
            role=OrganizationRoleEnum.STAFF,
        )
    )


def create_property(repo: PropertyRepository, org: Organization, *, name: str) -> Property:
    return repo.create(
        PropertyCreate(name=name, property_type=PropertyTypeEnum.PG, organization_id=org.id)
    )


def create_building(
    repo: BuildingRepository, org: Organization, prop: Property, *, name: str
) -> Building:
    return repo.create(
        BuildingCreate(
            organization_id=org.id, property_id=prop.id, name=name
        )
    )


def create_floor(
    repo: FloorRepository, org: Organization, building: Building, *, number: int
) -> Floor:
    return repo.create(
        FloorCreate(
            organization_id=org.id,
            building_id=building.id,
            floor_number=number,
            name=f"Floor {number}",
        )
    )


def create_room(
    repo: RoomRepository, org: Organization, floor: Floor, *, number: str
) -> Room:
    return repo.create(
        RoomCreate(
            organization_id=org.id,
            floor_id=floor.id,
            room_number=number,
            room_type=RoomTypeEnum.DOUBLE,
        )
    )


def create_bed(
    repo: BedRepository, org: Organization, room: Room, *, bed_number: str
) -> Bed:
    return repo.create(
        BedCreate(
            organization_id=org.id,
            room_id=room.id,
            bed_number=bed_number,
            status=BedStatusEnum.AVAILABLE,
        )
    )


def create_profile(
    repo: ResidentProfileRepository,
    org: Organization,
    member: OrganizationMember,
    prop: Property,
    *,
    contact: str,
) -> ResidentProfile:
    return repo.create(
        ResidentProfileCreate(
            organization_id=org.id,
            organization_member_id=member.id,
            property_id=prop.id,
            emergency_contact_name=contact,
            emergency_contact_phone="9999999999",
            address="12 Main St",
        )
    )


def seed_chain(db_session, *, slug: str = "abc-mall", contact: str = "Alice"):
    """One full chain: org → user → member → profile → property → building → floor → room."""
    org = create_org(OrganizationRepository(db_session), slug=slug)
    user = create_user(UserRepository(db_session), email=f"{slug}@example.com")
    member = create_member(OrganizationMemberRepository(db_session), org, user)
    prop = create_property(PropertyRepository(db_session), org, name=f"{slug} PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    floor = create_floor(FloorRepository(db_session), org, building, number=1)
    room = create_room(RoomRepository(db_session), org, floor, number="101")
    profile = create_profile(
        ResidentProfileRepository(db_session), org, member, prop, contact=contact
    )
    return org, prop, room, profile


def create_stay(
    db_session,
    org: Organization,
    prop: Property,
    profile: ResidentProfile,
    bed: Bed,
    *,
    start_date: date = date(2026, 1, 1),
    **overrides: object,
) -> TenantStay:
    return TenantStayRepository(db_session).create(
        TenantStayCreate(
            organization_id=org.id,
            resident_profile_id=profile.id,
            property_id=prop.id,
            bed_id=bed.id,
            start_date=start_date,
            **overrides,
        )
    )


def test_create_stay(db_session) -> None:
    org, prop, room, profile = seed_chain(db_session)
    bed = create_bed(BedRepository(db_session), org, room, bed_number="1")

    stay = create_stay(db_session, org, prop, profile, bed)
    assert stay.id is not None
    assert stay.organization_id == org.id
    assert stay.resident_profile_id == profile.id
    assert stay.property_id == prop.id
    assert stay.bed_id == bed.id
    assert stay.start_date == date(2026, 1, 1)
    assert stay.status == TenantStayStatusEnum.ACTIVE
    assert stay.end_date is None
    assert stay.notes is None
    assert stay.created_at is not None


def test_get_by_id(db_session) -> None:
    org, prop, room, profile = seed_chain(db_session)
    bed = create_bed(BedRepository(db_session), org, room, bed_number="1")
    stay = create_stay(db_session, org, prop, profile, bed)

    fetched = TenantStayRepository(db_session).get_by_id(stay.id)
    assert fetched is not None
    assert fetched.id == stay.id
    assert fetched.bed_id == bed.id

    assert TenantStayRepository(db_session).get_by_id(uuid4()) is None


def test_list_for_org_is_scoped_and_ordered(db_session) -> None:
    org_a, prop_a, room_a, profile_a = seed_chain(db_session, slug="abc-mall")
    org_b, prop_b, room_b, profile_b = seed_chain(db_session, slug="sunrise")

    bed_repo = BedRepository(db_session)
    bed_a1 = create_bed(bed_repo, org_a, room_a, bed_number="1")
    bed_a2 = create_bed(bed_repo, org_a, room_a, bed_number="2")
    bed_b1 = create_bed(bed_repo, org_b, room_b, bed_number="1")

    create_stay(db_session, org_a, prop_a, profile_a, bed_a1, start_date=date(2025, 1, 1))
    create_stay(db_session, org_a, prop_a, profile_a, bed_a2, start_date=date(2026, 1, 1))
    create_stay(db_session, org_b, prop_b, profile_b, bed_b1, start_date=date(2026, 6, 1))

    repo = TenantStayRepository(db_session)
    dates_a = [s.start_date for s in repo.list_for_org(org_a.id)]
    assert dates_a == [date(2026, 1, 1), date(2025, 1, 1)]
    assert [s.organization_id for s in repo.list_for_org(org_b.id)] == [org_b.id]


def test_list_for_resident(db_session) -> None:
    org, prop, room, profile = seed_chain(db_session, slug="abc-mall", contact="Alice")
    user_repo = UserRepository(db_session)
    member_repo = OrganizationMemberRepository(db_session)
    other_user = create_user(user_repo, email="carol@example.com")
    other_member = create_member(member_repo, org, other_user)
    other_profile = create_profile(
        ResidentProfileRepository(db_session),
        org,
        other_member,
        prop,
        contact="Carol",
    )

    bed_repo = BedRepository(db_session)
    bed1 = create_bed(bed_repo, org, room, bed_number="1")
    bed2 = create_bed(bed_repo, org, room, bed_number="2")

    create_stay(db_session, org, prop, profile, bed1, start_date=date(2025, 1, 1))
    create_stay(db_session, org, prop, profile, bed2, start_date=date(2026, 1, 1))
    create_stay(
        db_session,
        org,
        prop,
        other_profile,
        bed2,
        start_date=date(2024, 6, 1),
        status=TenantStayStatusEnum.COMPLETED,
        end_date=date(2024, 9, 1),
    )

    stays = TenantStayRepository(db_session).list_for_resident(profile.id)
    assert {s.bed_id for s in stays} == {bed1.id, bed2.id}
    assert [s.start_date for s in stays] == [date(2026, 1, 1), date(2025, 1, 1)]


def test_list_for_bed(db_session) -> None:
    org, prop, room, profile = seed_chain(db_session)
    bed_repo = BedRepository(db_session)
    bed1 = create_bed(bed_repo, org, room, bed_number="1")
    bed2 = create_bed(bed_repo, org, room, bed_number="2")

    create_stay(
        db_session,
        org,
        prop,
        profile,
        bed1,
        start_date=date(2025, 1, 1),
        status=TenantStayStatusEnum.COMPLETED,
        end_date=date(2025, 6, 1),
    )
    create_stay(db_session, org, prop, profile, bed1, start_date=date(2026, 1, 1))
    create_stay(db_session, org, prop, profile, bed2, start_date=date(2026, 6, 1))

    stays = TenantStayRepository(db_session).list_for_bed(bed1.id)
    assert [s.start_date for s in stays] == [date(2026, 1, 1), date(2025, 1, 1)]

    assert TenantStayRepository(db_session).list_for_bed(uuid4()) == []


def test_get_active_for_bed(db_session) -> None:
    org, prop, room, profile = seed_chain(db_session)
    bed1 = create_bed(BedRepository(db_session), org, room, bed_number="1")
    bed2 = create_bed(BedRepository(db_session), org, room, bed_number="2")

    active = create_stay(db_session, org, prop, profile, bed1)
    create_stay(
        db_session,
        org,
        prop,
        profile,
        bed1,
        start_date=date(2025, 1, 1),
        status=TenantStayStatusEnum.COMPLETED,
        end_date=date(2025, 6, 1),
    )

    assert TenantStayRepository(db_session).get_active_for_bed(bed1.id).id == active.id
    assert TenantStayRepository(db_session).get_active_for_bed(bed2.id) is None


def test_active_stay_unique_per_bed(db_session) -> None:
    org, prop, room, profile = seed_chain(db_session)
    bed = create_bed(BedRepository(db_session), org, room, bed_number="1")
    repo = TenantStayRepository(db_session)

    repo.create(
        TenantStayCreate(
            organization_id=org.id,
            resident_profile_id=profile.id,
            property_id=prop.id,
            bed_id=bed.id,
            start_date=date(2026, 1, 1),
        )
    )

    with pytest.raises(IntegrityError):
        repo.create(
            TenantStayCreate(
                organization_id=org.id,
                resident_profile_id=profile.id,
                property_id=prop.id,
                bed_id=bed.id,
                start_date=date(2026, 2, 1),
            )
        )
    db_session.rollback()

    completed = repo.create(
        TenantStayCreate(
            organization_id=org.id,
            resident_profile_id=profile.id,
            property_id=prop.id,
            bed_id=bed.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 1),
            status=TenantStayStatusEnum.COMPLETED,
        )
    )
    assert completed.status == TenantStayStatusEnum.COMPLETED
    assert repo.get_active_for_bed(bed.id) is not None