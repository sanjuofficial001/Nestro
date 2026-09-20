"""Tests for the bed repository on SQLite, verifying room scoping."""

from app.models.bed import Bed
from app.models.building import Building
from app.models.enums import BedStatusEnum, PropertyTypeEnum, RoomTypeEnum
from app.models.floor import Floor
from app.models.organization import Organization
from app.models.property import Property
from app.models.room import Room
from app.repositories.bed import BedRepository
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.property import PropertyRepository
from app.repositories.room import RoomRepository
from app.schemas.bed import BedCreate
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
) -> Floor:
    return repo.create(
        FloorCreate(
            organization_id=org.id,
            building_id=building.id,
            floor_number=1,
            name="First Floor",
        )
    )


def create_room(
    repo: RoomRepository,
    org: Organization,
    floor: Floor,
) -> Room:
    return repo.create(
        RoomCreate(
            organization_id=org.id,
            floor_id=floor.id,
            room_number="A101",
            room_type=RoomTypeEnum.FIVE_SHARE,
        )
    )


def create_bed(
    repo: BedRepository,
    org: Organization,
    room: Room,
    *,
    bed_number: str,
) -> Bed:
    return repo.create(
        BedCreate(organization_id=org.id, room_id=room.id, bed_number=bed_number)
    )


def seed_room(db_session) -> tuple[Organization, Room]:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    floor = create_floor(FloorRepository(db_session), org, building)
    room = create_room(RoomRepository(db_session), org, floor)
    return org, room


def test_create_bed(db_session) -> None:
    org, room = seed_room(db_session)
    bed = create_bed(BedRepository(db_session), org, room, bed_number="1")
    assert bed.id is not None
    assert bed.organization_id == org.id
    assert bed.room_id == room.id
    assert bed.bed_number == "1"
    assert bed.status is BedStatusEnum.AVAILABLE
    assert bed.created_at is not None


def test_list_for_room_is_scoped_and_ordered(db_session) -> None:
    org, room_a = seed_room(db_session)
    prop = create_property(PropertyRepository(db_session), org, name="PSG Girls PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Annex")
    floor = create_floor(FloorRepository(db_session), org, building)
    room_b = create_room(RoomRepository(db_session), org, floor)

    bed_repo = BedRepository(db_session)
    create_bed(bed_repo, org, room_a, bed_number="B3")
    create_bed(bed_repo, org, room_a, bed_number="B1")
    create_bed(bed_repo, org, room_b, bed_number="B1")

    numbers_a = [b.bed_number for b in bed_repo.list_for_room(room_a.id)]
    assert numbers_a == ["B1", "B3"]
    numbers_b = [b.bed_number for b in bed_repo.list_for_room(room_b.id)]
    assert numbers_b == ["B1"]


def test_get_by_id(db_session) -> None:
    org, room = seed_room(db_session)
    bed = create_bed(BedRepository(db_session), org, room, bed_number="1")
    fetched = BedRepository(db_session).get_by_id(bed.id)
    assert fetched is not None
    assert fetched.id == bed.id
    assert fetched.bed_number == "1"