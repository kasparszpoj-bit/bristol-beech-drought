"""QField project: freeze the issued field sample, and load the results.

The field sample issued on 29 September 2026 lives in the QField GeoPackage.
freeze_sample() copies its tree list (keyed by the council's stable ASSET_ID)
into raw.field_sample_frozen, once. It refuses to overwrite a different list,
because a sample already in the field must never change.

After a walk, the project folder exported from the phone is unzipped into
data/field_returns/<date>/ and load_returns() copies the scores, as
returned, into raw.field_returns:

    beech-load-field-returns data/field_returns/2026-09-30
"""

import sqlite3
import sys
from pathlib import Path

from beech.db import PROJECT_ROOT, apply_sql, connect

GPKG = PROJECT_ROOT / "qfield" / "beech_field_check" / "field_check.gpkg"
ISSUED_ON = "2026-09-29"


def read_issued_sample(gpkg: Path = GPKG) -> list[tuple[str, int, str, int]]:
    """(asset_id, tree_no, stratum, priority) for every tree in the project."""
    with sqlite3.connect(gpkg) as c:
        return c.execute(
            "SELECT asset_id, tree_no, stratum, priority FROM field_check "
            "ORDER BY tree_no"
        ).fetchall()


def freeze_sample(gpkg: Path = GPKG) -> int:
    rows = read_issued_sample(gpkg)
    with connect() as conn:
        existing = conn.execute(
            "SELECT asset_id, tree_no, stratum, priority "
            "FROM raw.field_sample_frozen ORDER BY tree_no"
        ).fetchall()
        if existing and [tuple(r) for r in existing] != rows:
            raise RuntimeError("a different frozen sample already exists; not overwriting")
        if not existing:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO raw.field_sample_frozen "
                    "(asset_id, tree_no, stratum, priority, issued_on, source) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    [(*r, ISSUED_ON, str(gpkg.name)) for r in rows],
                )
        conn.commit()
    return len(rows)


SCORES = ("found", "species_ok", "defoliation", "discolour", "dieback",
          "leaf_fall", "mast", "fungus", "photo", "notes", "survey_time", "surveyor")


def gpkg_wkb(blob: bytes) -> bytes:
    """The WKB inside a GeoPackage geometry blob, without the GP header."""
    if blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry")
    envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(blob[3] >> 1) & 0b111]
    return blob[8 + envelope:]


def photo_path(folder: Path, photo: str | None) -> str | None:
    """The photo's path relative to the project, wherever the export put it.

    QField records photos as DCIM/<name>.jpg; some exports flatten the folder.
    """
    if not photo:
        return None
    for candidate in (folder / photo, folder / Path(photo).name):
        if candidate.exists():
            return candidate.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    return photo


def read_returns(folder: Path) -> list[dict]:
    """Every visited tree (found is filled in) in a returned QField project."""
    gpkg = folder / "field_check.gpkg"
    # Read only: the returned files are the raw record and stay as they came.
    with sqlite3.connect(f"file:{gpkg.as_posix()}?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            f"SELECT asset_id, tree_no, {', '.join(SCORES)}, geom "
            "FROM field_check WHERE found IS NOT NULL ORDER BY tree_no"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["geom"] = gpkg_wkb(d["geom"])
        d["photo"] = photo_path(folder, d["photo"])
        d["notes"] = d["notes"].strip() if d["notes"] else None
        out.append(d)
    return out


def load_returns(folder: Path) -> int:
    rows = read_returns(folder)
    source = folder.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    cols = ("asset_id", "tree_no", *SCORES)
    with connect() as conn, conn.cursor() as cur:
        # Reloading the same file replaces its rows; other walks are untouched.
        cur.execute("DELETE FROM raw.field_returns WHERE return_file = %s", (source,))
        cur.executemany(
            f"INSERT INTO raw.field_returns ({', '.join(cols)}, geom, return_file) "
            f"VALUES ({', '.join(['%s'] * len(cols))}, "
            "ST_GeomFromWKB(%s, 27700), %s)",
            [(*(r[c] for c in cols), r["geom"], source) for r in rows],
        )
        conn.commit()
    return len(rows)


def returns_main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if folder is None or not (folder / "field_check.gpkg").exists():
        raise SystemExit("usage: beech-load-field-returns <folder with field_check.gpkg>")
    apply_sql(["01_schema.sql"])
    n = load_returns(folder)
    apply_sql(["07_field_check.sql"])
    print(f"loaded {n} visited trees from {folder}")


def main() -> None:
    apply_sql(["01_schema.sql"])
    n = freeze_sample()
    apply_sql(["05_field_sample.sql"])
    print(f"frozen field sample: {n} trees")


if __name__ == "__main__":
    main()
