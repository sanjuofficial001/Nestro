"""Service-layer resident profile CRUD: org membership and role enforcement."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import OrganizationRoleEnum, PropertyTypeEnum, RoleEnum
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.property import Property
from app.models.resident_profile import ResidentProfile
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.user import UserRepository
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.resident_profile_api import ResidentProfileUpdate
from app.schemas.user import UserCreate
from app.services.resident_profile_service import ResidentProfileService


def make_user(db_session, *, role: RoleEnum, email: str | None = None) -> User:
    user = UserRepository(db_session).create(
        UserCreate(
            email=email or f"{role.value.lower()}-{id(role)}@example.com",
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


def service(db_session) -> ResidentProfileService:
    return ResidentProfileService(db_session)


def create_payload(
    org, member, *, property_id=None, emergency_contact_name: str = "Asha Rao"
) -> ResidentProfileCreate:
    return ResidentProfileCreate(
        organization_id=org.id,
        organization_member_id=member.id,
        property_id=property_id,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_phone="9876543210",
        address="12 MG Road",
    )


def make_profile(
    db_session, org, member, *, property_id=None, emergency_contact_name: str = "Asha Rao"
) -> ResidentProfile:
    return ResidentProfileRepository(db_session).create(
        create_payload(
            org,
            member,
            property_id=property_id,
            emergency_contact_name=emergency_contact_name,
        ),
    )


def test_create_resident_profile_owner_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    profile = service(db_session).create_resident_profile(
        owner, create_payload(org, member, property_id=prop.id)
    )
    assert profile.id is not None
    assert profile.organization_id == org.id
    assert profile.organization_member_id == member.id
    assert profile.property_id == prop.id
    assert profile.is_active is True


def test_create_resident_profile_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)

    profile = service(db_session).create_resident_profile(
        manager, create_payload(org, member)
    )
    assert profile.emergency_contact_phone == "9876543210"


def test_create_resident_profile_super_admin_bypasses(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    profile = service(db_session).create_resident_profile(
        admin, create_payload(org, member)
    )
    assert profile.organization_id == org.id


def test_create_resident_profile_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_resident_profile(staff, create_payload(org, member))


def test_create_resident_profile_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_resident_profile(outsider, create_payload(org, member))


def test_create_resident_profile_missing_member_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="organization member not found"):
        service(db_session).create_resident_profile(
            owner,
            ResidentProfileCreate(
                organization_id=org.id,
                organization_member_id=uuid4(),
                emergency_contact_name="Asha Rao",
                emergency_contact_phone="9876543210",
                address="12 MG Road",
            ),
        )


def test_create_resident_profile_cross_org_member_raises(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member_b = make_member(db_session, org_b, resident)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(
        ValueError, match="organization member does not belong to this organization"
    ):
        service(db_session).create_resident_profile(
            owner, create_payload(org_a, member_b)
        )


def test_create_resident_profile_missing_property_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="property not found"):
        service(db_session).create_resident_profile(
            owner, create_payload(org, member, property_id=uuid4())
        )


def test_create_resident_profile_cross_org_property_raises(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org_a, resident)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(ValueError, match="property does not belong to this organization"):
        service(db_session).create_resident_profile(
            owner, create_payload(org_a, member, property_id=prop_b.id)
        )


def test_create_resident_profile_duplicate_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_profile(db_session, org, member)

    with pytest.raises(ValueError, match="resident profile already exists"):
        service(db_session).create_resident_profile(owner, create_payload(org, member))


def test_list_resident_profiles_member_sees_org(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    for name in ("Asha", "Bala"):
        resident = make_user(db_session, role=RoleEnum.TENANT, email=f"{name}@example.com")
        make_profile(
            db_session,
            org,
            make_member(db_session, org, resident),
            emergency_contact_name=name,
        )

    profiles = service(db_session).list_resident_profiles(owner, org.id)
    assert [p.emergency_contact_name for p in profiles] == ["Asha", "Bala"]


def test_list_resident_profiles_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    make_profile(db_session, org, make_member(db_session, org, resident))
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_resident_profiles(outsider, org.id)


def test_get_resident_profile_member_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    resident = make_user(db_session, role=RoleEnum.TENANT)
    profile = make_profile(db_session, org, make_member(db_session, org, resident))

    fetched = service(db_session).get_resident_profile(owner, profile.id)
    assert fetched.id == profile.id
    assert fetched.organization_id == org.id


def test_get_resident_profile_cross_org_denied(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    profile = make_profile(db_session, org_b, make_member(db_session, org_b, resident))
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).get_resident_profile(owner, profile.id)


def test_get_resident_profile_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="resident profile not found"):
        service(db_session).get_resident_profile(owner, uuid4())


def test_update_resident_profile_owner_succeeds_and_keeps_ids(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
    profile = make_profile(db_session, org, member)

    updated = service(db_session).update_resident_profile(
        owner,
        profile.id,
        ResidentProfileUpdate(
            property_id=prop.id,
            emergency_contact_name="  Asha Menon  ",
            address="  44 Cantonment  ",
            notes="  Prefers ground floor  ",
        ),
    )
    assert updated.property_id == prop.id
    assert updated.emergency_contact_name == "Asha Menon"
    assert updated.address == "44 Cantonment"
    assert updated.notes == "Prefers ground floor"
    assert updated.organization_id == org.id
    assert updated.organization_member_id == member.id


def test_update_resident_profile_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)
    resident = make_user(db_session, role=RoleEnum.TENANT)
    profile = make_profile(db_session, org, make_member(db_session, org, resident))

    updated = service(db_session).update_resident_profile(
        manager,
        profile.id,
        ResidentProfileUpdate(emergency_contact_phone="9000000000"),
    )
    assert updated.emergency_contact_phone == "9000000000"


def test_update_resident_profile_deactivates(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    resident = make_user(db_session, role=RoleEnum.TENANT)
    profile = make_profile(db_session, org, make_member(db_session, org, resident))

    updated = service(db_session).update_resident_profile(
        owner, profile.id, ResidentProfileUpdate(is_active=False)
    )
    assert updated.is_active is False


def test_update_resident_profile_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    resident = make_user(db_session, role=RoleEnum.TENANT)
    profile = make_profile(db_session, org, make_member(db_session, org, resident))
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_resident_profile(
            staff, profile.id, ResidentProfileUpdate(is_active=False)
        )


def test_update_resident_profile_cross_org_property_raises(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)
    resident = make_user(db_session, role=RoleEnum.TENANT)
    profile = make_profile(db_session, org_a, make_member(db_session, org_a, resident))

    with pytest.raises(ValueError, match="property does not belong to this organization"):
        service(db_session).update_resident_profile(
            owner, profile.id, ResidentProfileUpdate(property_id=prop_b.id)
        )


def test_update_resident_profile_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="resident profile not found"):
        service(db_session).update_resident_profile(
            owner, uuid4(), ResidentProfileUpdate(is_active=False)
        )