"""Service-layer bed CRUD: org membership, role enforcement, capacity absence."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import (
    BedStatusEnum,
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
    RoomTypeEnum,
)
from app.models.organization import Organization
from app.models.property import Property
from app.models.room import Room
from app.models.user import User
from app.repositories.bed import BedRepository
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.room import RoomRepository
from app.repositories.user import UserRepository
from app.schemas.bed import BedCreate, BedRead
from app.schemas.bed_api import BedUpdate
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.room import RoomCreate, RoomRead
from app.schemas.user import UserCreate
from app.services.bed_service import BedService


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


def make_room(db_session, org, floor) -> Room:
    return RoomRepository(db_session).create(
        RoomCreate(
            room_number="101",
            room_type=RoomTypeEnum.DOUBLE,
            organization_id=org.id,
            floor_id=floor.id,
        ),
    )


def make_bed(db_session, org, room, *, bed_number: str = "1"):
    return BedRepository(db_session).create(
        BedCreate(
            bed_number=bed_number,
            organization_id=org.id,
            room_id=room.id,
        ),
    )


def service(db_session) -> BedService:
    return BedService(db_session)


def create_payload(
    org, room, *, bed_number: str = "1", status: BedStatusEnum = BedStatusEnum.AVAILABLE
) -> BedCreate:
    return BedCreate(
        bed_number=bed_number,
        status=status,
        organization_id=org.id,
        room_id=room.id,
    )


def test_bed_update_has_no_capacity_field() -> None:
    assert "capacity" not in BedUpdate.model_fields
    assert "max_beds" not in BedUpdate.model_fields
    assert "bed_count" not in BedUpdate.model_fields


def test_bed_read_has_no_capacity_field() -> None:
    assert "capacity" not in BedRead.model_fields
    assert "max_beds" not in BedRead.model_fields
    assert "bed_count" not in BedRead.model_fields


def test_room_read_still_has_no_capacity_field() -> None:
    assert "capacity" not in RoomRead.model_fields
    assert "max_beds" not in RoomRead.model_fields
    assert "bed_count" not in RoomRead.model_fields


def test_create_bed_owner_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    bed = service(db_session).create_bed(owner, create_payload(org, room))
    assert bed.id is not None
    assert bed.room_id == room.id
    assert bed.organization_id == org.id


def test_create_bed_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)

    bed = service(db_session).create_bed(manager, create_payload(org, room))
    assert bed.bed_number == "1"


def test_create_bed_super_admin_bypasses(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    bed = service(db_session).create_bed(admin, create_payload(org, room))
    assert bed.organization_id == org.id


def test_create_bed_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_bed(staff, create_payload(org, room))


def test_create_bed_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_bed(outsider, create_payload(org, room))


def test_create_bed_duplicate_number_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_bed(db_session, org, room, bed_number="1")

    with pytest.raises(ValueError, match="bed already exists"):
        service(db_session).create_bed(owner, create_payload(org, room))


def test_create_bed_missing_room_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="room not found"):
        service(db_session).create_bed(
            owner,
            BedCreate(
                bed_number="1",
                organization_id=org.id,
                room_id=uuid4(),
            ),
        )


def test_create_bed_cross_org_room_raises(db_session) -> None:
    org_a = make_org(db_session, slug="abc-pg")
    org_b = make_org(db_session, slug="sunrise")
    prop_b = make_property(db_session, org_b, name="Sunrise Apartments")
    building_b = make_building(db_session, org_b, prop_b, name="Tower")
    floor_b = make_floor(db_session, org_b, building_b)
    room_b = make_room(db_session, org_b, floor_b)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org_a, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(ValueError, match="room does not belong to this organization"):
        service(db_session).create_bed(owner, create_payload(org_a, room_b))


def test_list_beds_member_sees_room_beds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_bed(db_session, org, room, bed_number="1")
    make_bed(db_session, org, room, bed_number="2")
    make_bed(db_session, org, room, bed_number="3")

    beds = service(db_session).list_beds(owner, org.id, room.id)
    assert [b.bed_number for b in beds] == ["1", "2", "3"]


def test_list_beds_non_member_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    make_bed(db_session, org, room)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_beds(outsider, org.id, room.id)


def test_get_bed_member_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    bed = make_bed(db_session, org, room)

    fetched = service(db_session).get_bed(owner, bed.id)
    assert fetched.id == bed.id
    assert fetched.organization_id == org.id


def test_get_bed_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="bed not found"):
        service(db_session).get_bed(owner, uuid4())


def test_update_bed_owner_succeeds_and_keeps_room_org(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    bed = make_bed(db_session, org, room, bed_number="1")

    updated = service(db_session).update_bed(
        owner,
        bed.id,
        BedUpdate(bed_number="  A1  ", status=BedStatusEnum.BLOCKED),
    )
    assert updated.bed_number == "A1"
    assert updated.status == BedStatusEnum.BLOCKED
    assert updated.organization_id == org.id
    assert updated.room_id == room.id


def test_update_bed_manager_succeeds(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    manager = make_user(db_session, role=RoleEnum.MANAGER)
    make_member(db_session, org, manager, role=OrganizationRoleEnum.MANAGER)
    bed = make_bed(db_session, org, room)

    updated = service(db_session).update_bed(manager, bed.id, BedUpdate(bed_number="2"))
    assert updated.bed_number == "2"


def test_update_bed_status_success(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    bed = make_bed(db_session, org, room)

    updated = service(db_session).update_bed(
        owner,
        bed.id,
        BedUpdate(status=BedStatusEnum.MAINTENANCE),
    )
    assert updated.status == BedStatusEnum.MAINTENANCE


def test_update_bed_staff_denied(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    staff = make_user(db_session, role=RoleEnum.STAFF)
    make_member(db_session, org, staff, role=OrganizationRoleEnum.STAFF)
    bed = make_bed(db_session, org, room)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_bed(staff, bed.id, BedUpdate(bed_number="999"))


def test_update_bed_immutable_room_id(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    bed = make_bed(db_session, org, room)

    updated = service(db_session).update_bed(owner, bed.id, BedUpdate(bed_number="2"))
    assert updated.room_id == room.id


def test_update_bed_immutable_organization_id(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    bed = make_bed(db_session, org, room)

    updated = service(db_session).update_bed(owner, bed.id, BedUpdate(bed_number="2"))
    assert updated.organization_id == org.id


def test_update_bed_duplicate_number_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    prop = make_property(db_session, org)
    building = make_building(db_session, org, prop)
    floor = make_floor(db_session, org, building)
    room = make_room(db_session, org, floor)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    make_bed(db_session, org, room, bed_number="1")
    other = make_bed(db_session, org, room, bed_number="2")

    with pytest.raises(ValueError, match="bed already exists"):
        service(db_session).update_bed(owner, other.id, BedUpdate(bed_number="1"))


def test_update_bed_missing_raises(db_session) -> None:
    org = make_org(db_session, slug="abc-pg")
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)

    with pytest.raises(NotFoundError, match="bed not found"):
        service(db_session).update_bed(owner, uuid4(), BedUpdate(bed_number="999"))