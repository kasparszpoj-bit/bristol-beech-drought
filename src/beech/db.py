"""Database connection and SQL file runner.

The password is never held in this repo. libpq reads it from the user's
pgpass file (%APPDATA%\\postgresql\\pgpass.conf on Windows).
"""

import os
import sys
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"

DSN = os.environ.get(
    "BEECH_DSN", "host=localhost port=5432 dbname=beech user=postgres"
)


def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(DSN, autocommit=autocommit)


def apply_sql(names: list[str] | None = None) -> list[str]:
    """Run the numbered SQL files in sql/, in order. Returns the files run."""
    files = sorted(SQL_DIR.glob("[0-9][0-9]_*.sql"))
    if names:
        files = [f for f in files if f.name in names]
    with connect() as conn:
        for f in files:
            conn.execute(f.read_text(encoding="utf-8"))
        conn.commit()
    return [f.name for f in files]


def apply_sql_cli() -> None:
    for name in apply_sql(sys.argv[1:] or None):
        print(f"applied {name}")
