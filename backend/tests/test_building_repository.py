"""Tests for the building repository on SQLite, verifying property scoping."""

from app.models.building import Building
from app.models.enums import PropertyTypeEnum
from app.models.organization import Organization
from app.models.property import Property
from app.repositories.building import BuildingRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.property import PropertyRepository
from app.schemas.building import BuildingCreate
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


def test_create_building(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    assert building.id is not None
    assert building.organization_id == org.id
    assert building.property_id == prop.id
    assert building.name == "Block A"
    assert building.description is None
    assert building.created_at is not None
    assert building.updated_at is not None


def test_list_for_property_is_scoped(db_session) -> None:
    org_repo = OrganizationRepository(db_session)
    org = create_org(org_repo, slug="abc-mall")
    prop_repo = PropertyRepository(db_session)
    prop_a = create_property(prop_repo, org, name="PSG Boys PG")
    prop_b = create_property(prop_repo, org, name="PSG Girls PG")

    building_repo = BuildingRepository(db_session)
    create_building(building_repo, org, prop_a, name="Block A")
    create_building(building_repo, org, prop_a, name="Block B")
    create_building(building_repo, org, prop_b, name="Annex")

    names_a = [b.name for b in building_repo.list_for_property(prop_a.id)]
    assert names_a == ["Block A", "Block B"]
    names_b = [b.name for b in building_repo.list_for_property(prop_b.id)]
    assert names_b == ["Annex"]


def test_get_by_id(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    building = create_building(BuildingRepository(db_session), org, prop, name="Block A")
    fetched = BuildingRepository(db_session).get_by_id(building.id)
    assert fetched is not None
    assert fetched.id == building.id
    assert fetched.name == "Block A"