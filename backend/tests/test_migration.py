"""Test that the committed Alembic migration applies cleanly and creates users."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_alembic_upgrade(tmp_path: Path) -> Path:
    db = tmp_path / "migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite+pysqlite:///{db}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return db


def test_upgrade_head_creates_expected_tables(tmp_path: Path) -> None:
    db = run_alembic_upgrade(tmp_path)
    conn = sqlite3.connect(db)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table'"
            )
        }
        assert {
            "users",
            "organizations",
            "organization_members",
            "properties",
            "buildings",
            "floors",
            "rooms",
            "beds",
        } <= tables
        assert "alembic_version" in tables

        user_columns = {
            row[1]
            for row in conn.execute("pragma table_info(users)")
        }
        assert {
            "id",
            "email",
            "phone",
            "full_name",
            "role",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        } <= user_columns

        org_columns = {
            row[1]
            for row in conn.execute("pragma table_info(organizations)")
        }
        assert {
            "id",
            "name",
            "slug",
            "is_active",
            "created_at",
            "updated_at",
        } <= org_columns

        member_columns = {
            row[1]
            for row in conn.execute("pragma table_info(organization_members)")
        }
        assert {
            "id",
            "organization_id",
            "user_id",
            "role",
            "created_at",
            "updated_at",
        } <= member_columns

        property_columns = {
            row[1]
            for row in conn.execute("pragma table_info(properties)")
        }
        assert {
            "id",
            "organization_id",
            "name",
            "property_type",
            "address",
            "contact_phone",
            "rules",
            "status",
            "deleted_at",
            "created_at",
            "updated_at",
        } <= property_columns

        building_columns = {
            row[1]
            for row in conn.execute("pragma table_info(buildings)")
        }
        assert {
            "id",
            "organization_id",
            "property_id",
            "name",
            "description",
            "created_at",
            "updated_at",
        } <= building_columns

        floor_columns = {
            row[1]
            for row in conn.execute("pragma table_info(floors)")
        }
        assert {
            "id",
            "organization_id",
            "building_id",
            "floor_number",
            "name",
            "created_at",
            "updated_at",
        } <= floor_columns

        room_columns = {
            row[1]
            for row in conn.execute("pragma table_info(rooms)")
        }
        assert {
            "id",
            "organization_id",
            "floor_id",
            "room_number",
            "room_type",
            "created_at",
            "updated_at",
        } <= room_columns
        assert "capacity" not in room_columns
        assert "max_beds" not in room_columns

        bed_columns = {
            row[1]
            for row in conn.execute("pragma table_info(beds)")
        }
        assert {
            "id",
            "organization_id",
            "room_id",
            "bed_number",
            "status",
            "created_at",
            "updated_at",
        } <= bed_columns

        fk_targets = {
            table: {
                row[2]
                for row in conn.execute(f"pragma foreign_key_list({table})")
            }
            for table in ["buildings", "floors", "rooms", "beds"]
        }
        assert fk_targets["buildings"] == {"organizations", "properties"}
        assert fk_targets["floors"] == {"buildings", "organizations"}
        assert fk_targets["rooms"] == {"floors", "organizations"}
        assert fk_targets["beds"] == {"organizations", "rooms"}

        version = conn.execute("select version_num from alembic_version").fetchone()
        assert version is not None and version[0]
    finally:
        conn.close()