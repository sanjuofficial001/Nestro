"""Service-layer property CRUD: org membership + role enforcement."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import (
    OrganizationRoleEnum,
    PropertyStatusEnum,
    PropertyTypeEnum,
    RoleEnum,
)
from app.models.organization import Organization
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.user import UserRepository
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.property_api import PropertyUpdate
from app.schemas.user import UserCreate
from app.services.property_service import PropertyService


def make_user(db_session, *, role: RoleEnum) -> User:
    user = UserRepository(db_session).create(
        UserCreate(
            email=f"{role.value.lower()}-{id(role)}@example.com",
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


def make_member(db_session, org, user, *, role: OrganizationRoleEnum) -> None:
    OrganizationMemberRepository(db_session).create(
        OrganizationMemberCreate(organization_id=org.id, user_id=user.id, role=role),
    )


def make_property(db_session, org, *, name: str) -> None:
    PropertyRepository(db_session).create(
        PropertyCreate(
            name=name,
            property_type=PropertyTypeEnum.PG,
            organization_id=org.id,
        ),
    )


def service(db_session) -> PropertyService:
    return PropertyService(db_session)


def create_payload(org, *, name: str) -> PropertyCreate:
    return PropertyCreate(
        name=name,
        property_type=PropertyTypeEnum.PG,
        organization_id=org.id,
    )


def test_create_property_owner_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    property = service(db_session).create_property(owner, create_payload(org, name="PSG Boys PG"))
    assert property.id is not None
    assert property.organization_id == org.id
    assert property.property_type is PropertyTypeEnum.PG


def test_create_property_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)

    property = service(db_session).create_property(
        manager,
        create_payload(org, name="Elite Hostel"),
    )
    assert property.name == "Elite Hostel"


def test_create_property_super_admin_bypasses(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    property = service(db_session).create_property(admin, create_payload(org, name="Admin PG"))
    assert property.organization_id == org.id


def test_create_property_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_property(staff, create_payload(org, name="Staff PG"))


def test_create_property_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_property(outsider, create_payload(org, name="Outsider PG"))


def test_create_property_duplicate_name_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_property(db_session, org, name="PSG Boys PG")

    with pytest.raises(ValueError, match="property already exists"):
        service(db_session).create_property(owner, create_payload(org, name="PSG Boys PG"))


def test_list_properties_scoped_to_org(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)
    make_property(db_session, org_a, name="PSG Boys PG")
    make_property(db_session, org_a, name="PSG Girls PG")
    make_property(db_session, org_b, name="Sunrise Apartments")

    names = {p.name for p in service(db_session).list_properties(owner, org_a.id)}
    assert names == {"PSG Boys PG", "PSG Girls PG"}


def test_list_properties_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_property(db_session, org, name="PSG Boys PG")

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_properties(outsider, org.id)


def test_get_property_member_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_property(db_session, org, name="PSG Boys PG")
    property = PropertyRepository(db_session).list_for_org(org.id)[0]

    fetched = service(db_session).get_property(owner, property.id)
    assert fetched.id == property.id
    assert fetched.organization_id == org.id


def test_get_property_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError):
        service(db_session).get_property(owner, uuid4())


def test_get_property_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_property(db_session, org, name="PSG Boys PG")
    property = PropertyRepository(db_session).list_for_org(org.id)[0]

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).get_property(outsider, property.id)


def test_update_property_owner_succeeds_and_keeps_org_type(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_property(db_session, org, name="PSG Boys PG")
    property = PropertyRepository(db_session).list_for_org(org.id)[0]
    original_type = property.property_type

    updated = service(db_session).update_property(
        owner,
        property.id,
        PropertyUpdate(
            name="  PSG Boys Renamed  ",
            status=PropertyStatusEnum.INACTIVE,
        ),
    )
    assert updated.name == "PSG Boys Renamed"
    assert updated.status is PropertyStatusEnum.INACTIVE
    assert updated.organization_id == org.id
    assert updated.property_type is original_type


def test_update_property_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)
    make_property(db_session, org, name="PSG Boys PG")
    property = PropertyRepository(db_session).list_for_org(org.id)[0]

    updated = service(db_session).update_property(
        manager,
        property.id,
        PropertyUpdate(rules="No visitors after 10pm"),
    )
    assert updated.rules == "No visitors after 10pm"


def test_update_property_super_admin_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)
    make_property(db_session, org, name="PSG Boys PG")
    property = PropertyRepository(db_session).list_for_org(org.id)[0]

    updated = service(db_session).update_property(
        admin,
        property.id,
        PropertyUpdate(name="Admin Renamed"),
    )
    assert updated.name == "Admin Renamed"


def test_update_property_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)
    make_property(db_session, org, name="PSG Boys PG")
    property = PropertyRepository(db_session).list_for_org(org.id)[0]

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_property(staff, property.id, PropertyUpdate(name="Nope"))


def test_update_property_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError):
        service(db_session).update_property(owner, uuid4(), PropertyUpdate(name="Nope"))