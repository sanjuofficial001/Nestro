"""Service-layer floor CRUD: org membership + role enforcement."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import OrganizationRoleEnum, PropertyTypeEnum, RoleEnum
from app.models.organization import Organization
from app.models.property import Property
from app.models.user import User
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.user import UserRepository
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.floor_api import FloorUpdate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.user import UserCreate
from app.services.floor_service import FloorService


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


def make_building(db_session, org, prop, *, name: str = "Block A"):
    return BuildingRepository(db_session).create(
        BuildingCreate(name=name, organization_id=org.id, property_id=prop.id),
    )


def make_floor(db_session, org, building, *, floor_number: int, name: str = "Ground") -> None:
    FloorRepository(db_session).create(
        FloorCreate(
            floor_number=floor_number,
            name=name,
            organization_id=org.id,
            building_id=building.id,
        ),
    )


def service(db_session) -> FloorService:
    return FloorService(db_session)


def create_payload(org, building, *, floor_number: int, name: str = "Ground") -> FloorCreate:
    return FloorCreate(
        floor_number=floor_number,
        name=name,
        organization_id=org.id,
        building_id=building.id,
    )


def test_create_floor_owner_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    floor = service(db_session).create_floor(owner, create_payload(org, building, floor_number=0))
    assert floor.id is not None
    assert floor.building_id == building.id
    assert floor.organization_id == org.id


def test_create_floor_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)

    floor = service(db_session).create_floor(
        manager,
        create_payload(org, building, floor_number=1, name="First"),
    )
    assert floor.name == "First"


def test_create_floor_super_admin_bypasses(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    floor = service(db_session).create_floor(admin, create_payload(org, building, floor_number=0))
    assert floor.organization_id == org.id


def test_create_floor_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_floor(staff, create_payload(org, building, floor_number=0))


def test_create_floor_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_floor(outsider, create_payload(org, building, floor_number=0))


def test_create_floor_duplicate_number_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_floor(db_session, org, building, floor_number=0)

    with pytest.raises(ValueError, match="floor already exists"):
        service(db_session).create_floor(owner, create_payload(org, building, floor_number=0))


def test_create_floor_missing_building_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="building not found"):
        service(db_session).create_floor(
            owner,
            FloorCreate(
                floor_number=0,
                name="Ground",
                organization_id=org.id,
                building_id=uuid4(),
            ),
        )


def test_create_floor_cross_org_building_raises(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    building_b = make_building(db_session, org_b, prop_b, name="Tower")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(ValueError, match="building does not belong to this organization"):
        service(db_session).create_floor(owner, create_payload(org_a, building_b, floor_number=0))


def test_list_floors_member_sees_building_floors(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_floor(db_session, org, building, floor_number=0, name="Ground")
    make_floor(db_session, org, building, floor_number=1, name="First")
    make_floor(db_session, org, building, floor_number=2, name="Second")

    floors = service(db_session).list_floors(owner, org.id, building.id)
    assert [f.floor_number for f in floors] == [0, 1, 2]


def test_list_floors_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    make_floor(db_session, org, building, floor_number=0)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_floors(outsider, org.id, building.id)


def test_list_floors_foreign_org_building_denied(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    building_b = make_building(db_session, org_b, prop_b, name="Tower")
    make_floor(db_session, org_b, building_b, floor_number=0)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="building not found"):
        service(db_session).list_floors(owner, org_a.id, building_b.id)


def test_get_floor_member_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_floor(db_session, org, building, floor_number=0)
    floor = FloorRepository(db_session).list_for_building(building.id)[0]

    fetched = service(db_session).get_floor(owner, floor.id)
    assert fetched.id == floor.id
    assert fetched.organization_id == org.id


def test_get_floor_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    make_floor(db_session, org, building, floor_number=0)
    floor = FloorRepository(db_session).list_for_building(building.id)[0]
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).get_floor(outsider, floor.id)


def test_get_floor_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="floor not found"):
        service(db_session).get_floor(owner, uuid4())


def test_update_floor_owner_succeeds_and_keeps_building_org(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_floor(db_session, org, building, floor_number=0, name="Ground")
    floor = FloorRepository(db_session).list_for_building(building.id)[0]

    updated = service(db_session).update_floor(
        owner,
        floor.id,
        FloorUpdate(floor_number=1, name="  First  "),
    )
    assert updated.floor_number == 1
    assert updated.name == "First"
    assert updated.organization_id == org.id
    assert updated.building_id == building.id


def test_update_floor_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)
    make_floor(db_session, org, building, floor_number=0)
    floor = FloorRepository(db_session).list_for_building(building.id)[0]

    updated = service(db_session).update_floor(
        manager,
        floor.id,
        FloorUpdate(name="Lobby"),
    )
    assert updated.name == "Lobby"


def test_update_floor_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)
    make_floor(db_session, org, building, floor_number=0)
    floor = FloorRepository(db_session).list_for_building(building.id)[0]

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_floor(staff, floor.id, FloorUpdate(name="Nope"))


def test_update_floor_duplicate_number_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_floor(db_session, org, building, floor_number=0, name="Ground")
    make_floor(db_session, org, building, floor_number=1, name="First")
    floor_zero = [
        f for f in FloorRepository(db_session).list_for_building(building.id) if f.floor_number == 0
    ][0]

    with pytest.raises(ValueError, match="floor already exists"):
        service(db_session).update_floor(owner, floor_zero.id, FloorUpdate(floor_number=1))


def test_update_floor_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="floor not found"):
        service(db_session).update_floor(owner, uuid4(), FloorUpdate(name="Nope"))