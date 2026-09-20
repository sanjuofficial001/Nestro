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


def test_upgrade_head_creates_users_table(tmp_path: Path) -> None:
    db = run_alembic_upgrade(tmp_path)
    conn = sqlite3.connect(db)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table'"
            )
        }
        assert "users" in tables
        assert "alembic_version" in tables
        columns = {
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
        } <= columns
        version = conn.execute("select version_num from alembic_version").fetchone()
        assert version is not None and version[0]
    finally:
        conn.close()