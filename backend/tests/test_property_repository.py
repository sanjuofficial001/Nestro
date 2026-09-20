"""Tests for the property repository on SQLite, verifying org scoping."""

from app.models.enums import PropertyTypeEnum
from app.models.organization import Organization
from app.models.property import Property
from app.repositories.organization import OrganizationRepository
from app.repositories.property import PropertyRepository
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


def test_create_property(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    property = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")
    assert property.id is not None
    assert property.organization_id == org.id
    assert property.property_type is PropertyTypeEnum.PG
    assert property.status.value == "ACTIVE"
    assert property.created_at is not None
    assert property.deleted_at is None


def test_list_for_org_is_scoped(db_session) -> None:
    org_repo = OrganizationRepository(db_session)
    org_a = create_org(org_repo, slug="abc-mall")
    org_b = create_org(org_repo, slug="sunrise")

    prop_repo = PropertyRepository(db_session)
    create_property(prop_repo, org_a, name="PSG Boys PG")
    create_property(prop_repo, org_a, name="PSG Girls PG")
    create_property(prop_repo, org_b, name="Sunrise Apartments")

    names_a = {p.name for p in prop_repo.list_for_org(org_a.id)}
    assert names_a == {"PSG Boys PG", "PSG Girls PG"}
    names_b = {p.name for p in prop_repo.list_for_org(org_b.id)}
    assert names_b == {"Sunrise Apartments"}


def test_exists_by_name_scoped(db_session) -> None:
    org_repo = OrganizationRepository(db_session)
    org_a = create_org(org_repo, slug="abc-mall")
    org_b = create_org(org_repo, slug="sunrise")

    prop_repo = PropertyRepository(db_session)
    create_property(prop_repo, org_a, name="PSG Boys PG")

    assert prop_repo.exists_by_name(org_a.id, "PSG Boys PG") is True
    assert prop_repo.exists_by_name(org_a.id, "Missing") is False
    assert prop_repo.exists_by_name(org_b.id, "PSG Boys PG") is False


def test_get_by_id(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    prop_repo = PropertyRepository(db_session)
    property = create_property(prop_repo, org, name="PSG Boys PG")
    fetched = prop_repo.get_by_id(property.id)
    assert fetched is not None
    assert fetched.id == property.id