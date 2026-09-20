"""Tests for the floor repository on SQLite, verifying building scoping."""

from app.models.building import Building
from app.models.enums import PropertyTypeEnum
from app.models.floor import Floor
from app.models.organization import Organization
from app.models.property import Property
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.property import PropertyRepository
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.property import PropertyCreate


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
    name: str,
) -> Floor:
    return repo.create(
        FloorCreate(
            organization_id=org.id,
            building_id=building.id,
            floor_number=floor_number,
            name=name,
        )
    )


def test_create_floor(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    floor = create_floor(
        FloorRepository(db_session), org, building, floor_number=1, name="First Floor"
    )
    assert floor.id is not None
    assert floor.organization_id == org.id
    assert floor.building_id == building.id
    assert floor.floor_number == 1
    assert floor.name == "First Floor"
    assert floor.created_at is not None


def test_list_for_building_is_scoped_and_ordered(db_session) -> None:
    org_repo = OrganizationRepository(db_session)
    org = create_org(org_repo, slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building_repo = BuildingRepository(db_session)
    block_a = create_building(building_repo, org, prop, name="Block A")
    block_b = create_building(building_repo, org, prop, name="Block B")

    floor_repo = FloorRepository(db_session)
    create_floor(floor_repo, org, block_a, floor_number=2, name="Second Floor")
    create_floor(floor_repo, org, block_a, floor_number=0, name="Ground Floor")
    create_floor(floor_repo, org, block_b, floor_number=1, name="First Floor")

    numbers_a = [f.floor_number for f in floor_repo.list_for_building(block_a.id)]
    assert numbers_a == [0, 2]
    numbers_b = [f.floor_number for f in floor_repo.list_for_building(block_b.id)]
    assert numbers_b == [1]


def test_get_by_id(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    floor = create_floor(
        FloorRepository(db_session), org, building, floor_number=1, name="First Floor"
    )
    fetched = FloorRepository(db_session).get_by_id(floor.id)
    assert fetched is not None
    assert fetched.id == floor.id
    assert fetched.floor_number == 1