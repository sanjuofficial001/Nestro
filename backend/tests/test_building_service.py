"""Service-layer building CRUD: org membership + role enforcement."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import OrganizationRoleEnum, PropertyTypeEnum, RoleEnum
from app.models.organization import Organization
from app.models.property import Property
from app.models.user import User
from app.repositories.building import BuildingRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.user import UserRepository
from app.schemas.building import BuildingCreate
from app.schemas.building_api import BuildingUpdate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.user import UserCreate
from app.services.building_service import BuildingService


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


def make_property(db_session, org, *, name: str = "PSG Boys PG") -> Property:
    return PropertyRepository(db_session).create(
        PropertyCreate(
            name=name,
            property_type=PropertyTypeEnum.PG,
            organization_id=org.id,
        ),
    )


def make_building(db_session, org, prop, *, name: str) -> None:
    BuildingRepository(db_session).create(
        BuildingCreate(name=name, organization_id=org.id, property_id=prop.id),
    )


def service(db_session) -> BuildingService:
    return BuildingService(db_session)


def create_payload(org, prop, *, name: str) -> BuildingCreate:
    return BuildingCreate(name=name, organization_id=org.id, property_id=prop.id)


def test_create_building_owner_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    building = service(db_session).create_building(owner, create_payload(org, prop, name="Block A"))
    assert building.id is not None
    assert building.property_id == prop.id
    assert building.organization_id == org.id


def test_create_building_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)

    building = service(db_session).create_building(
        manager,
        create_payload(org, prop, name="Block B"),
    )
    assert building.name == "Block B"


def test_create_building_super_admin_bypasses(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    building = service(db_session).create_building(
        admin,
        create_payload(org, prop, name="Admin Block"),
    )
    assert building.organization_id == org.id


def test_create_building_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_building(staff, create_payload(org, prop, name="Nope"))


def test_create_building_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_building(outsider, create_payload(org, prop, name="Nope"))


def test_create_building_duplicate_name_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_building(db_session, org, prop, name="Block A")

    with pytest.raises(ValueError, match="building already exists"):
        service(db_session).create_building(owner, create_payload(org, prop, name="Block A"))


def test_create_building_missing_property_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="property not found"):
        service(db_session).create_building(
            owner,
            BuildingCreate(name="Block A", organization_id=org.id, property_id=uuid4()),
        )


def test_create_building_cross_org_property_raises(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(ValueError, match="property does not belong to this organization"):
        service(db_session).create_building(
            owner,
            BuildingCreate(name="Block A", organization_id=org_a.id, property_id=prop_b.id),
        )


def test_list_buildings_member_sees_property_buildings(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop_a = make_property(db_session, org, name="PSG Boys PG")
    prop_b = make_property(db_session, org, name="PSG Girls PG")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_building(db_session, org, prop_a, name="Block A")
    make_building(db_session, org, prop_a, name="Block B")
    make_building(db_session, org, prop_b, name="Annex")

    names = [b.name for b in service(db_session).list_buildings(owner, org.id, prop_a.id)]
    assert names == ["Block A", "Block B"]


def test_list_buildings_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    make_building(db_session, org, prop, name="Block A")
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_buildings(outsider, org.id, prop.id)


def test_list_buildings_foreign_org_property_denied(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    make_building(db_session, org_b, prop_b, name="Lobby")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="property not found"):
        service(db_session).list_buildings(owner, org_a.id, prop_b.id)


def test_get_building_member_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_building(db_session, org, prop, name="Block A")
    building = BuildingRepository(db_session).list_for_property(prop.id)[0]

    fetched = service(db_session).get_building(owner, building.id)
    assert fetched.id == building.id
    assert fetched.organization_id == org.id


def test_get_building_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    make_building(db_session, org, prop, name="Block A")
    building = BuildingRepository(db_session).list_for_property(prop.id)[0]
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).get_building(outsider, building.id)


def test_get_building_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="building not found"):
        service(db_session).get_building(owner, uuid4())


def test_update_building_owner_succeeds_and_keeps_org_prop(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_building(db_session, org, prop, name="Block A")
    building = BuildingRepository(db_session).list_for_property(prop.id)[0]

    updated = service(db_session).update_building(
        owner,
        building.id,
        BuildingUpdate(name="  Block A Renamed  ", description="North wing"),
    )
    assert updated.name == "Block A Renamed"
    assert updated.description == "North wing"
    assert updated.organization_id == org.id
    assert updated.property_id == prop.id


def test_update_building_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)
    make_building(db_session, org, prop, name="Block A")
    building = BuildingRepository(db_session).list_for_property(prop.id)[0]

    updated = service(db_session).update_building(
        manager,
        building.id,
        BuildingUpdate(description="East wing"),
    )
    assert updated.description == "East wing"


def test_update_building_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)
    make_building(db_session, org, prop, name="Block A")
    building = BuildingRepository(db_session).list_for_property(prop.id)[0]

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_building(staff, building.id, BuildingUpdate(name="Nope"))


def test_update_building_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="building not found"):
        service(db_session).update_building(owner, uuid4(), BuildingUpdate(name="Nope"))