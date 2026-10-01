import psycopg
import pytest

from beech.db import apply_sql, connect


@pytest.fixture(scope="session")
def db():
    """A connection with the SQL functions installed. Skips if no database."""
    try:
        conn = connect(autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostGIS database not reachable: {exc}")
    apply_sql(["01_schema.sql"])
    # Install only the functions from 02_clean.sql, not the table rebuilds,
    # so the tests never depend on (or change) loaded data.
    from beech.db import SQL_DIR

    text = (SQL_DIR / "02_clean.sql").read_text(encoding="utf-8")
    for block in text.split("CREATE OR REPLACE FUNCTION")[1:]:
        body = "CREATE OR REPLACE FUNCTION" + block.split("$$;")[0] + "$$;"
        conn.execute(body)
    yield conn
    conn.close()
