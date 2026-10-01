"""Load the Bristol City Council tree register into raw.register_trees.

Source: ArcGIS REST MapServer/32, Open Government Licence 3.0. The service
returns at most 1,000 records per request, so results are paged in OBJECTID
order. Attributes are stored untouched as jsonb; all cleaning is in SQL.
"""

import json
from collections.abc import Iterator

import requests

from beech.db import apply_sql, connect

SERVICE = (
    "https://maps2.bristol.gov.uk/server2/rest/services/"
    "ext/ll_environment_and_planning/MapServer/32"
)
# The whole register is loaded: the five comparison genera are picked out in
# SQL, and every other tree is still needed as a neighbour when touching
# crowns are split between trees.
GENERA: tuple[str, ...] = ()
COMPARISON_GENERA = ("Fagus", "Quercus", "Tilia", "Platanus", "Acer pseudoplatanus")
PAGE_SIZE = 1000

# ONS local authority boundaries, May 2026, generalised and clipped to the
# coastline. Bristol is E06000023.
BOUNDARY_SERVICE = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Local_Authority_Districts_May_2026_Boundaries_UK_BGC/FeatureServer/0"
)
BRISTOL_CODE = "E06000023"


def load_bristol_boundary(conn, session: requests.Session) -> None:
    r = session.get(
        f"{BOUNDARY_SERVICE}/query",
        params={
            "where": f"LAD26CD = '{BRISTOL_CODE}'",
            "outFields": "LAD26CD,LAD26NM",
            "outSR": 27700,
            "f": "geojson",
        },
        timeout=60,
    )
    r.raise_for_status()
    features = r.json().get("features", [])
    if len(features) != 1:
        raise RuntimeError(f"expected one Bristol boundary, got {len(features)}")
    f = features[0]
    run_id = conn.execute(
        "INSERT INTO qa.ingest_log (source, where_clause, service_count, "
        "loaded_count, finished_at) VALUES (%s, %s, 1, 1, now()) RETURNING run_id",
        (BOUNDARY_SERVICE, f"LAD26CD = '{BRISTOL_CODE}'"),
    ).fetchone()[0]
    # GeoJSON output is labelled WGS84 by the spec, but outSR=27700 returns
    # British National Grid coordinates, so the SRID is set, not transformed.
    conn.execute(
        "INSERT INTO raw.boundaries (code, name, source, geom, run_id) "
        "VALUES (%s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 27700)), %s) "
        "ON CONFLICT (code) DO UPDATE SET geom = EXCLUDED.geom, "
        "run_id = EXCLUDED.run_id",
        (
            f["properties"]["LAD26CD"],
            f["properties"]["LAD26NM"],
            BOUNDARY_SERVICE,
            json.dumps(f["geometry"]),
            run_id,
        ),
    )


def where_clause(genera: tuple[str, ...] = GENERA) -> str:
    """Filter on genus; an empty tuple means every record."""
    if not genera:
        return "1=1"
    return " OR ".join(f"LATIN_NAME LIKE '{g}%'" for g in genera)


def fetch_count(session: requests.Session, where: str) -> int:
    r = session.get(
        f"{SERVICE}/query",
        params={"where": where, "returnCountOnly": "true", "f": "json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["count"]


def fetch_features(session: requests.Session, where: str) -> Iterator[dict]:
    offset = 0
    while True:
        r = session.get(
            f"{SERVICE}/query",
            params={
                "where": where,
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 27700,
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
                "f": "json",
            },
            timeout=120,
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(f"service error at offset {offset}: {body['error']}")
        features = body.get("features", [])
        yield from features
        if len(features) < PAGE_SIZE and not body.get("exceededTransferLimit"):
            return
        offset += len(features)


def feature_to_row(feature: dict) -> tuple[int, str, float, float]:
    """(objectid, attributes as JSON text, easting, northing)."""
    attrs = feature["attributes"]
    geom = feature.get("geometry") or {}
    x = geom.get("x", attrs.get("X"))
    y = geom.get("y", attrs.get("Y"))
    if x is None or y is None:
        raise ValueError(f"no coordinates for OBJECTID {attrs.get('OBJECTID')}")
    return int(attrs["OBJECTID"]), json.dumps(attrs), float(x), float(y)


def main() -> None:
    apply_sql(["01_schema.sql"])
    where = where_clause()
    session = requests.Session()
    expected = fetch_count(session, where)

    with connect() as conn:
        run_id = conn.execute(
            "INSERT INTO qa.ingest_log (source, where_clause, service_count) "
            "VALUES (%s, %s, %s) RETURNING run_id",
            (SERVICE, where, expected),
        ).fetchone()[0]

        rows = [feature_to_row(f) for f in fetch_features(session, where)]
        ids = [r[0] for r in rows]
        if len(ids) != len(set(ids)):
            raise RuntimeError("duplicate OBJECTIDs returned while paging")

        conn.execute("TRUNCATE raw.register_trees")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO raw.register_trees (objectid, attributes, geom, run_id) "
                "VALUES (%s, %s::jsonb, "
                "ST_SetSRID(ST_MakePoint(%s, %s), 27700), %s)",
                [(*r, run_id) for r in rows],
            )
        conn.execute(
            "UPDATE qa.ingest_log SET loaded_count = %s, finished_at = now() "
            "WHERE run_id = %s",
            (len(rows), run_id),
        )
        load_bristol_boundary(conn, session)
        conn.commit()

    print(f"run {run_id}: service reports {expected}, loaded {len(rows)}")
    if len(rows) != expected:
        raise SystemExit("loaded count does not match the service count")

    # 02_clean.sql rebuilds clean.trees, which drops the views built on it,
    # so every numbered SQL file is reapplied in order.
    applied = apply_sql()
    print("clean.trees rebuilt; reapplied", ", ".join(applied))


if __name__ == "__main__":
    main()
