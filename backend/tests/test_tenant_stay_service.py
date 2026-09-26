"""Service-layer tenant stay CRUD: org membership, role enforcement, and the
status/end_date lifecycle rules."""

from datetime import date
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.bed import Bed
from app.models.enums import (
    BedStatusEnum,
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
    RoomTypeEnum,
    TenantStayStatusEnum,
)
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.property import Property
from app.models.resident_profile import ResidentProfile
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
from app.schemas.tenant_stay_api import TenantStayUpdate
from app.schemas.user import UserCreate
from app.services.tenant_stay_service import TenantStayService


def make_user(db_session, *, role: RoleEnum, email: str | None = None) -> User:
    user = UserRepository(db_session).create(
        UserCreate(
            email=email or f"{role.value.lower()}-{uuid4().hex[:8]}@example.com",
            phone=None,
            full_name="Test User",
            role=role,
        ),
    )
    db_session.commit()
    db_session.refresh(user)
    return user


def make_org(db_session, *, slug: str) -> Organization:
    return OrganizationRepository(db_session).create(
        OrganizationCreate(name=slug.title(), slug=slug),
    )


def make_member(
    db_session, org, user, *, role: OrganizationRoleEnum = OrganizationRoleEnum.STAFF
) -> OrganizationMember:
    return OrganizationMemberRepository(db_session).create(
        OrganizationMemberCreate(organization_id=org.id, user_id=user.id, role=role),
    )


def make_property(db_session, org, *, name: str = "PSG Boys PG") -> Property:
    return PropertyRepository(db_session).create(
        PropertyCreate(
            name=name,
            property_type=PropertyTypeEnum.PG,
            organization_id=org.id,
        ),
    )


def make_profile(db_session, org, *, property_id=None) -> ResidentProfile:
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    return ResidentProfileRepository(db_session).create(
        ResidentProfileCreate(
            organization_id=org.id,
            organization_member_id=member.id,
            property_id=property_id,
            emergency_contact_name="Asha Rao",
            emergency_contact_phone="9876543210",
            address="12 MG Road",
        ),
    )


def make_bed(db_session, org, prop, *, bed_number: str = "1") -> Bed:
    building = BuildingRepository(db_session).create(
        BuildingCreate(organization_id=org.id, property_id=prop.id, name=f"B-{bed_number}"),
    )
    floor = FloorRepository(db_session).create(
        FloorCreate(
            organization_id=org.id,
            building_id=building.id,
            floor_number=1,
            name="Floor 1",
        ),
    )
    room = RoomRepository(db_session).create(
        RoomCreate(
            organization_id=org.id,
            floor_id=floor.id,
            room_number=f"R-{bed_number}",
            room_type=RoomTypeEnum.DOUBLE,
        ),
    )
    return BedRepository(db_session).create(
        BedCreate(
            organization_id=org.id,
            room_id=room.id,
            bed_number=bed_number,
            status=BedStatusEnum.AVAILABLE,
        ),
    )


def service(db_session) -> TenantStayService:
    return TenantStayService(db_session)


def create_payload(
    org,
    profile: ResidentProfile,
    prop: Property,
    bed: Bed,
    *,
    start_date: date = date(2026, 1, 1),
    **overrides: object,
) -> TenantStayCreate:
    return TenantStayCreate(
        organization_id=org.id,
        resident_profile_id=profile.id,
        property_id=prop.id,
        bed_id=bed.id,
        start_date=start_date,
        **overrides,
    )


def seed_owner(db_session, *, slug: str = "abc-pg"):
    org = make_org(db_session, slug=slug)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    return org, owner


def make_stay(db_session, org, profile, prop, bed, **overrides: object) -> TenantStay:
    return TenantStayRepository(db_session).create(
        create_payload(org, profile, prop, bed, **overrides),
    )


def test_create_tenant_stay_owner_succeeds(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop, bed_number="1")
    profile = make_profile(db_session, org, property_id=prop.id)

    stay = service(db_session).create_tenant_stay(
        owner, create_payload(org, profile, prop, bed)
    )
    assert stay.id is not None
    assert stay.organization_id == org.id
    assert stay.resident_profile_id == profile.id
    assert stay.property_id == prop.id
    assert stay.bed_id == bed.id
    assert stay.status == TenantStayStatusEnum.ACTIVE
    assert stay.end_date is None


def test_create_tenant_stay_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)

    stay = service(db_session).create_tenant_stay(
        manager, create_payload(org, profile, prop, bed)
    )
    assert stay.status == TenantStayStatusEnum.ACTIVE


def test_create_tenant_stay_super_admin_bypasses(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)

    stay = service(db_session).create_tenant_stay(
        admin, create_payload(org, profile, prop, bed)
    )
    assert stay.organization_id == org.id


def test_create_tenant_stay_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_tenant_stay(
            staff, create_payload(org, profile, prop, bed)
        )


def test_create_tenant_stay_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_tenant_stay(
            outsider, create_payload(org, profile, prop, bed)
        )


def test_create_tenant_stay_missing_resident_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)

    with pytest.raises(NotFoundError, match="resident profile not found"):
        service(db_session).create_tenant_stay(
            owner,
            TenantStayCreate(
                organization_id=org.id,
                resident_profile_id=uuid4(),
                property_id=prop.id,
                bed_id=bed.id,
                start_date=date(2026, 1, 1),
            ),
        )


def test_create_tenant_stay_cross_org_resident_raises(db_session) -> None:
    org_a, owner = seed_owner(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_a = make_property(db_session, org_a)
    bed_a = make_bed(db_session, org_a, prop_a)
    profile_b = make_profile(db_session, org_b)

    with pytest.raises(
        ValueError, match="resident profile does not belong to this organization"
    ):
        service(db_session).create_tenant_stay(
            owner, create_payload(org_a, profile_b, prop_a, bed_a)
        )


def test_create_tenant_stay_missing_bed_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    profile = make_profile(db_session, org)

    with pytest.raises(NotFoundError, match="bed not found"):
        service(db_session).create_tenant_stay(
            owner,
            TenantStayCreate(
                organization_id=org.id,
                resident_profile_id=profile.id,
                property_id=prop.id,
                bed_id=uuid4(),
                start_date=date(2026, 1, 1),
            ),
        )


def test_create_tenant_stay_cross_org_bed_raises(db_session) -> None:
    org_a, owner = seed_owner(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_a = make_property(db_session, org_a)
    profile_a = make_profile(db_session, org_a)
    prop_b = make_property(db_session, org_b, name="Sunrise PG")
    bed_b = make_bed(db_session, org_b, prop_b, bed_number="9")

    with pytest.raises(ValueError, match="bed does not belong to this organization"):
        service(db_session).create_tenant_stay(
            owner, create_payload(org_a, profile_a, prop_a, bed_b)
        )


def test_create_tenant_stay_missing_property_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)

    with pytest.raises(NotFoundError, match="property not found"):
        service(db_session).create_tenant_stay(
            owner,
            TenantStayCreate(
                organization_id=org.id,
                resident_profile_id=profile.id,
                property_id=uuid4(),
                bed_id=bed.id,
                start_date=date(2026, 1, 1),
            ),
        )


def test_create_tenant_stay_cross_org_property_raises(db_session) -> None:
    org_a, owner = seed_owner(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_a = make_property(db_session, org_a)
    bed = make_bed(db_session, org_a, prop_a, bed_number="8")
    profile = make_profile(db_session, org_a)
    prop_b = make_property(db_session, org_b, name="Sunrise PG")

    with pytest.raises(ValueError, match="property does not belong to this organization"):
        service(db_session).create_tenant_stay(
            owner, create_payload(org_a, profile, prop_b, bed)
        )


def test_create_tenant_stay_property_must_match_bed(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    other_prop = make_property(db_session, org, name="Annex PG")
    bed = make_bed(db_session, org, prop, bed_number="7")
    profile = make_profile(db_session, org)

    with pytest.raises(ValueError, match="bed does not belong to the property"):
        service(db_session).create_tenant_stay(
            owner, create_payload(org, profile, other_prop, bed)
        )


def test_create_tenant_stay_second_active_on_bed_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop, bed_number="5")
    profile = make_profile(db_session, org)
    make_stay(db_session, org, profile, prop, bed)

    with pytest.raises(ValueError, match="bed already has an active stay"):
        service(db_session).create_tenant_stay(
            owner,
            create_payload(
                org, profile, prop, bed, start_date=date(2026, 2, 1)
            ),
        )


def test_create_tenant_stay_closed_history_allowed(db_session) -> None:
    """A closed stay may share a bed with the current active stay."""
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop, bed_number="6")
    profile = make_profile(db_session, org)
    make_stay(db_session, org, profile, prop, bed)

    past = service(db_session).create_tenant_stay(
        owner,
        create_payload(
            org,
            profile,
            prop,
            bed,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            status=TenantStayStatusEnum.CANCELLED,
        ),
    )
    assert past.status == TenantStayStatusEnum.CANCELLED
    assert past.end_date == date(2024, 6, 1)


def test_create_tenant_stay_end_date_before_start_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)

    with pytest.raises(ValueError, match="end_date must not precede start_date"):
        service(db_session).create_tenant_stay(
            owner,
            create_payload(
                org,
                profile,
                prop,
                bed,
                end_date=date(2025, 1, 1),
                status=TenantStayStatusEnum.COMPLETED,
            ),
        )


def test_create_tenant_stay_active_with_end_date_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)

    with pytest.raises(ValueError, match="an active stay cannot have an end_date"):
        service(db_session).create_tenant_stay(
            owner, create_payload(org, profile, prop, bed, end_date=date(2026, 6, 1))
        )


@pytest.mark.parametrize("status", [TenantStayStatusEnum.COMPLETED, TenantStayStatusEnum.CANCELLED])
def test_create_tenant_stay_closed_without_end_date_raises(
    db_session, status: TenantStayStatusEnum
) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)

    with pytest.raises(ValueError, match="a closed stay requires an end_date"):
        service(db_session).create_tenant_stay(
            owner, create_payload(org, profile, prop, bed, status=status)
        )


def test_list_tenant_stays_scoped_to_org(db_session) -> None:
    org_a, owner = seed_owner(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_a = make_property(db_session, org_a)
    bed_a = make_bed(db_session, org_a, prop_a, bed_number="1")
    bed_a2 = make_bed(db_session, org_a, prop_a, bed_number="2")
    profile_a = make_profile(db_session, org_a)
    prop_b = make_property(db_session, org_b, name="Sunrise PG")
    bed_b = make_bed(db_session, org_b, prop_b, bed_number="3")
    profile_b = make_profile(db_session, org_b)

    make_stay(db_session, org_a, profile_a, prop_a, bed_a, start_date=date(2025, 1, 1))
    make_stay(db_session, org_a, profile_a, prop_a, bed_a2, start_date=date(2026, 1, 1))
    make_stay(db_session, org_b, profile_b, prop_b, bed_b, start_date=date(2026, 6, 1))

    stays = service(db_session).list_tenant_stays(owner, org_a.id)
    assert [s.start_date for s in stays] == [date(2026, 1, 1), date(2025, 1, 1)]
    assert {s.organization_id for s in stays} == {org_a.id}


def test_list_tenant_stays_filters_by_resident(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed1 = make_bed(db_session, org, prop, bed_number="1")
    bed2 = make_bed(db_session, org, prop, bed_number="2")
    profile = make_profile(db_session, org)
    other = make_profile(db_session, org)

    make_stay(db_session, org, profile, prop, bed1)
    make_stay(db_session, org, other, prop, bed2)

    stays = service(db_session).list_tenant_stays(
        owner, org.id, resident_profile_id=profile.id
    )
    assert [s.bed_id for s in stays] == [bed1.id]


def test_list_tenant_stays_filters_by_bed(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed1 = make_bed(db_session, org, prop, bed_number="1")
    bed2 = make_bed(db_session, org, prop, bed_number="2")
    profile = make_profile(db_session, org)

    make_stay(
        db_session,
        org,
        profile,
        prop,
        bed1,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 6, 1),
        status=TenantStayStatusEnum.COMPLETED,
    )
    make_stay(db_session, org, profile, prop, bed1, start_date=date(2026, 1, 1))
    make_stay(db_session, org, profile, prop, bed2)

    stays = service(db_session).list_tenant_stays(owner, org.id, bed_id=bed1.id)
    assert [s.start_date for s in stays] == [date(2026, 1, 1), date(2025, 1, 1)]


def test_list_tenant_stays_filters_by_status(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed1 = make_bed(db_session, org, prop, bed_number="1")
    bed2 = make_bed(db_session, org, prop, bed_number="2")
    profile = make_profile(db_session, org)

    make_stay(db_session, org, profile, prop, bed1)
    make_stay(
        db_session,
        org,
        profile,
        prop,
        bed2,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 1),
        status=TenantStayStatusEnum.CANCELLED,
    )

    active = service(db_session).list_tenant_stays(
        owner, org.id, status=TenantStayStatusEnum.ACTIVE
    )
    assert [s.bed_id for s in active] == [bed1.id]

    cancelled = service(db_session).list_tenant_stays(
        owner, org.id, status=TenantStayStatusEnum.CANCELLED
    )
    assert [s.bed_id for s in cancelled] == [bed2.id]


def test_list_tenant_stays_foreign_org_resident_filter_raises(db_session) -> None:
    org_a, owner = seed_owner(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    profile_b = make_profile(db_session, org_b)

    with pytest.raises(NotFoundError, match="resident profile not found"):
        service(db_session).list_tenant_stays(
            owner, org_a.id, resident_profile_id=profile_b.id
        )


def test_list_tenant_stays_foreign_org_bed_filter_raises(db_session) -> None:
    org_a, owner = seed_owner(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise PG")
    bed_b = make_bed(db_session, org_b, prop_b, bed_number="9")

    with pytest.raises(NotFoundError, match="bed not found"):
        service(db_session).list_tenant_stays(owner, org_a.id, bed_id=bed_b.id)


def test_list_tenant_stays_non_member_denied(db_session) -> None:
    org, _ = seed_owner(db_session)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_tenant_stays(outsider, org.id)


def test_get_tenant_stay_succeeds(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)

    fetched = service(db_session).get_tenant_stay(owner, stay.id)
    assert fetched.id == stay.id
    assert fetched.organization_id == org.id


def test_get_tenant_stay_missing_raises(db_session) -> None:
    org, owner = seed_owner(db_session)

    with pytest.raises(NotFoundError, match="tenant stay not found"):
        service(db_session).get_tenant_stay(owner, uuid4())


def test_get_tenant_stay_cross_org_denied(db_session) -> None:
    org_a, _ = seed_owner(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise PG")
    bed_b = make_bed(db_session, org_b, prop_b, bed_number="9")
    profile_b = make_profile(db_session, org_b)
    stay_b = make_stay(db_session, org_b, profile_b, prop_b, bed_b)
    owner_a = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner_a, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).get_tenant_stay(owner_a, stay_b.id)


def test_update_tenant_stay_completes_active_stay(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)

    updated = service(db_session).update_tenant_stay(
        owner,
        stay.id,
        TenantStayUpdate(
            status=TenantStayStatusEnum.COMPLETED, end_date=date(2026, 6, 30)
        ),
    )
    assert updated.status == TenantStayStatusEnum.COMPLETED
    assert updated.end_date == date(2026, 6, 30)
    assert updated.bed_id == bed.id
    assert updated.start_date == date(2026, 1, 1)
    assert updated.organization_id == org.id
    assert updated.resident_profile_id == profile.id
    assert updated.property_id == prop.id

    # Closing frees the bed for a new check-in.
    assert TenantStayRepository(db_session).get_active_for_bed(bed.id) is None
    later = service(db_session).create_tenant_stay(
        owner, create_payload(org, profile, prop, bed, start_date=date(2026, 7, 1))
    )
    assert later.status == TenantStayStatusEnum.ACTIVE


def test_update_tenant_stay_cancels_active_stay(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)

    updated = service(db_session).update_tenant_stay(
        owner,
        stay.id,
        TenantStayUpdate(
            status=TenantStayStatusEnum.CANCELLED, end_date=date(2026, 3, 1)
        ),
    )
    assert updated.status == TenantStayStatusEnum.CANCELLED
    assert updated.end_date == date(2026, 3, 1)


def test_update_tenant_stay_closed_to_closed_allowed(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(
        db_session,
        org,
        profile,
        prop,
        bed,
        end_date=date(2026, 6, 1),
        status=TenantStayStatusEnum.COMPLETED,
    )

    updated = service(db_session).update_tenant_stay(
        owner, stay.id, TenantStayUpdate(status=TenantStayStatusEnum.CANCELLED)
    )
    assert updated.status == TenantStayStatusEnum.CANCELLED
    assert updated.end_date == date(2026, 6, 1)


def test_update_tenant_stay_notes_only(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)

    updated = service(db_session).update_tenant_stay(
        owner, stay.id, TenantStayUpdate(notes="  Prefers ground floor  ")
    )
    assert updated.notes == "Prefers ground floor"
    assert updated.status == TenantStayStatusEnum.ACTIVE
    assert updated.end_date is None
    assert updated.bed_id == bed.id


@pytest.mark.parametrize("closed", [TenantStayStatusEnum.COMPLETED, TenantStayStatusEnum.CANCELLED])
def test_update_tenant_stay_reopen_rejected(
    db_session, closed: TenantStayStatusEnum
) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(
        db_session, org, profile, prop, bed, end_date=date(2026, 6, 1), status=closed
    )

    with pytest.raises(ValueError, match="a closed stay cannot be reopened"):
        service(db_session).update_tenant_stay(
            owner, stay.id, TenantStayUpdate(status=TenantStayStatusEnum.ACTIVE)
        )


def test_update_tenant_stay_active_bed_collision_rejected(db_session) -> None:
    """Reopening is refused even when the bed is free again — history is final."""
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    old = make_stay(
        db_session,
        org,
        profile,
        prop,
        bed,
        end_date=date(2026, 6, 1),
        status=TenantStayStatusEnum.COMPLETED,
    )
    make_stay(db_session, org, profile, prop, bed, start_date=date(2026, 7, 1))

    with pytest.raises(ValueError, match="a closed stay cannot be reopened"):
        service(db_session).update_tenant_stay(
            owner, old.id, TenantStayUpdate(status=TenantStayStatusEnum.ACTIVE)
        )


def test_update_tenant_stay_end_date_without_status_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)

    with pytest.raises(ValueError, match="an active stay cannot have an end_date"):
        service(db_session).update_tenant_stay(
            owner, stay.id, TenantStayUpdate(end_date=date(2026, 6, 1))
        )


def test_update_tenant_stay_close_without_end_date_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)

    with pytest.raises(ValueError, match="a closed stay requires an end_date"):
        service(db_session).update_tenant_stay(
            owner, stay.id, TenantStayUpdate(status=TenantStayStatusEnum.COMPLETED)
        )


def test_update_tenant_stay_end_date_before_start_raises(db_session) -> None:
    org, owner = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)

    with pytest.raises(ValueError, match="end_date must not precede start_date"):
        service(db_session).update_tenant_stay(
            owner,
            stay.id,
            TenantStayUpdate(
                status=TenantStayStatusEnum.COMPLETED, end_date=date(2025, 12, 31)
            ),
        )


def test_update_tenant_stay_staff_denied(db_session) -> None:
    org, _ = seed_owner(db_session)
    prop = make_property(db_session, org)
    bed = make_bed(db_session, org, prop)
    profile = make_profile(db_session, org)
    stay = make_stay(db_session, org, profile, prop, bed)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_tenant_stay(
            staff, stay.id, TenantStayUpdate(notes="nope")
        )


def test_update_tenant_stay_missing_raises(db_session) -> None:
    org, owner = seed_owner(db_session)

    with pytest.raises(NotFoundError, match="tenant stay not found"):
        service(db_session).update_tenant_stay(
            owner, uuid4(), TenantStayUpdate(notes="nope")
        )
