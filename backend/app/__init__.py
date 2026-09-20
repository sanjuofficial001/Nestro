"""Application package for the Nestro FastAPI backend.

Layers (imports are always absolute from this package):
  api/ -> routes and request handling (no business logic, no DB access)
  core/ -> configuration and cross-cutting concerns
  db/ -> persistence foundation (declarative Base, Alembic target)
  models/ -> SQLAlchemy models
  repositories/ -> data access
  schemas/ -> Pydantic request/response models
  services/ -> business logic
"""