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
        assert {"users", "organizations", "organization_members"} <= tables
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

        version = conn.execute("select version_num from alembic_version").fetchone()
        assert version is not None and version[0]
    finally:
        conn.close()