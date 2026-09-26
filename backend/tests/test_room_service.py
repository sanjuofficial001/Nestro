"""Service-layer room CRUD: org membership, role enforcement, capacity absence."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import (
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
    RoomTypeEnum,
)
from app.models.organization import Organization
from app.models.property import Property
from app.models.user import User
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.room import RoomRepository
from app.repositories.user import UserRepository
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.room import RoomCreate, RoomRead
from app.schemas.room_api import RoomUpdate
from app.schemas.user import UserCreate
from app.services.room_service import RoomService


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


def make_floor(db_session, org, building, *, floor_number: int = 0):
    return FloorRepository(db_session).create(
        FloorCreate(
            floor_number=floor_number,
            name="Ground",
            organization_id=org.id,
            building_id=building.id,
        ),
    )


def make_room(db_session, org, floor, *, room_number: str = "101"):
    return RoomRepository(db_session).create(
        RoomCreate(
            room_number=room_number,
            room_type=RoomTypeEnum.DOUBLE,
            organization_id=org.id,
            floor_id=floor.id,
        ),
    )


def service(db_session) -> RoomService:
    return RoomService(db_session)


def create_payload(
    org, floor, *, room_number: str = "101", room_type: RoomTypeEnum = RoomTypeEnum.DOUBLE
) -> RoomCreate:
    return RoomCreate(
        room_number=room_number,
        room_type=room_type,
        organization_id=org.id,
        floor_id=floor.id,
    )


def test_room_update_has_no_capacity_field() -> None:
    assert "capacity" not in RoomUpdate.model_fields
    assert "max_beds" not in RoomUpdate.model_fields
    assert "bed_count" not in RoomUpdate.model_fields


def test_room_read_has_no_capacity_field() -> None:
    assert "capacity" not in RoomRead.model_fields
    assert "max_beds" not in RoomRead.model_fields
    assert "bed_count" not in RoomRead.model_fields


def test_create_room_owner_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    room = service(db_session).create_room(owner, create_payload(org, floor))
    assert room.id is not None
    assert room.floor_id == floor.id
    assert room.organization_id == org.id


def test_create_room_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)

    room = service(db_session).create_room(manager, create_payload(org, floor))
    assert room.room_number == "101"


def test_create_room_super_admin_bypasses(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    room = service(db_session).create_room(admin, create_payload(org, floor))
    assert room.organization_id == org.id


def test_create_room_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_room(staff, create_payload(org, floor))


def test_create_room_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_room(outsider, create_payload(org, floor))


def test_create_room_duplicate_number_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_room(db_session, org, floor, room_number="101")

    with pytest.raises(ValueError, match="room already exists"):
        service(db_session).create_room(owner, create_payload(org, floor))


def test_create_room_missing_floor_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="floor not found"):
        service(db_session).create_room(
            owner,
            RoomCreate(
                room_number="101",
                room_type=RoomTypeEnum.DOUBLE,
                organization_id=org.id,
                floor_id=uuid4(),
            ),
        )


def test_create_room_cross_org_floor_raises(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    building_b = make_building(db_session, org_b, prop_b, name="Tower")
    floor_b = make_floor(db_session, org_b, building_b, floor_number=3)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(ValueError, match="floor does not belong to this organization"):
        service(db_session).create_room(owner, create_payload(org_a, floor_b))


def test_list_rooms_member_sees_floor_rooms(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_room(db_session, org, floor, room_number="101")
    make_room(db_session, org, floor, room_number="102")
    make_room(db_session, org, floor, room_number="103")

    rooms = service(db_session).list_rooms(owner, org.id, floor.id)
    assert [r.room_number for r in rooms] == ["101", "102", "103"]


def test_list_rooms_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    make_room(db_session, org, floor)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_rooms(outsider, org.id, floor.id)


def test_get_room_member_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    room = make_room(db_session, org, floor)

    fetched = service(db_session).get_room(owner, room.id)
    assert fetched.id == room.id
    assert fetched.organization_id == org.id


def test_get_room_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="room not found"):
        service(db_session).get_room(owner, uuid4())


def test_update_room_owner_succeeds_and_keeps_floor_org(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    room = make_room(db_session, org, floor, room_number="101")

    updated = service(db_session).update_room(
        owner,
        room.id,
        RoomUpdate(room_number="  201  ", room_type=RoomTypeEnum.SINGLE),
    )
    assert updated.room_number == "201"
    assert updated.room_type == RoomTypeEnum.SINGLE
    assert updated.organization_id == org.id
    assert updated.floor_id == floor.id


def test_update_room_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)
    room = make_room(db_session, org, floor)

    updated = service(db_session).update_room(
        manager,
        room.id,
        RoomUpdate(room_type=RoomTypeEnum.TRIPLE),
    )
    assert updated.room_type == RoomTypeEnum.TRIPLE


def test_update_room_room_type_success(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    room = make_room(db_session, org, floor)

    updated = service(db_session).update_room(
        owner,
        room.id,
        RoomUpdate(room_type=RoomTypeEnum.FOUR_SHARE),
    )
    assert updated.room_type == RoomTypeEnum.FOUR_SHARE


def test_update_room_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)
    room = make_room(db_session, org, floor)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_room(staff, room.id, RoomUpdate(room_number="999"))


def test_update_room_immutable_floor_id(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    room = make_room(db_session, org, floor)

    updated = service(db_session).update_room(
        owner,
        room.id,
        RoomUpdate(room_number="202"),
    )
    assert updated.floor_id == floor.id


def test_update_room_immutable_organization_id(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    room = make_room(db_session, org, floor)

    updated = service(db_session).update_room(
        owner,
        room.id,
        RoomUpdate(room_number="202"),
    )
    assert updated.organization_id == org.id


def test_update_room_duplicate_number_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_room(db_session, org, floor, room_number="101")
    other = make_room(db_session, org, floor, room_number="102")

    with pytest.raises(ValueError, match="room already exists"):
        service(db_session).update_room(owner, other.id, RoomUpdate(room_number="101"))


def test_update_room_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="room not found"):
        service(db_session).update_room(owner, uuid4(), RoomUpdate(room_number="999"))