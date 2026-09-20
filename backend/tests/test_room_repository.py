"""Tests for the room repository on SQLite, verifying floor scoping."""

from app.models.building import Building
from app.models.enums import PropertyTypeEnum, RoomTypeEnum
from app.models.floor import Floor
from app.models.organization import Organization
from app.models.property import Property
from app.models.room import Room
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.property import PropertyRepository
from app.repositories.room import RoomRepository
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.property import PropertyCreate
from app.schemas.room import RoomCreate


def create_org(repo: OrganizationRepository, *, slug: str) -> Organization:
    return repo.create(OrganizationCreate(name=slug.title(), slug=slug))


def create_property(
    repo: PropertyRepository,
    org: Organization,
    *,
    name: str,
) -> Property:
    return repo.create(
        PropertyCreate(name=name, property_type=PropertyTypeEnum.PG, organization_id=org.id)
    )


def create_building(
    repo: BuildingRepository,
    org: Organization,
    prop: Property,
    *,
    name: str,
) -> Building:
    return repo.create(
        BuildingCreate(name=name, organization_id=org.id, property_id=prop.id)
    )


def create_floor(
    repo: FloorRepository,
    org: Organization,
    building: Building,
    *,
    floor_number: int,
) -> Floor:
    return repo.create(
        FloorCreate(
            organization_id=org.id,
            building_id=building.id,
            floor_number=floor_number,
            name=f"Floor {floor_number}",
        )
    )


def create_room(
    repo: RoomRepository,
    org: Organization,
    floor: Floor,
    *,
    room_number: str,
    room_type: RoomTypeEnum = RoomTypeEnum.FOUR_SHARE,
) -> Room:
    return repo.create(
        RoomCreate(
            organization_id=org.id,
            floor_id=floor.id,
            room_number=room_number,
            room_type=room_type,
        )
    )


def test_create_room(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    floor = create_floor(FloorRepository(db_session), org, building, floor_number=1)

    room = create_room(RoomRepository(db_session), org, floor, room_number="A101")
    assert room.id is not None
    assert room.organization_id == org.id
    assert room.floor_id == floor.id
    assert room.room_number == "A101"
    assert room.room_type is RoomTypeEnum.FOUR_SHARE
    assert room.created_at is not None


def test_list_for_floor_is_scoped_and_ordered(db_session) -> None:
    org_repo = OrganizationRepository(db_session)
    org = create_org(org_repo, slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building_repo = BuildingRepository(db_session)
    building = create_building(building_repo, org, prop, name="Block A")
    floor_repo = FloorRepository(db_session)
    floor_a = create_floor(floor_repo, org, building, floor_number=1)
    floor_b = create_floor(floor_repo, org, building, floor_number=2)

    room_repo = RoomRepository(db_session)
    create_room(room_repo, org, floor_a, room_number="A103")
    create_room(room_repo, org, floor_a, room_number="A101")
    create_room(room_repo, org, floor_b, room_number="B201")

    numbers_a = [r.room_number for r in room_repo.list_for_floor(floor_a.id)]
    assert numbers_a == ["A101", "A103"]
    numbers_b = [r.room_number for r in room_repo.list_for_floor(floor_b.id)]
    assert numbers_b == ["B201"]


def test_get_by_id(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    floor = create_floor(FloorRepository(db_session), org, building, floor_number=1)
    room = create_room(RoomRepository(db_session), org, floor, room_number="A101")
    fetched = RoomRepository(db_session).get_by_id(room.id)
    assert fetched is not None
    assert fetched.id == room.id
    assert fetched.room_number == "A101"