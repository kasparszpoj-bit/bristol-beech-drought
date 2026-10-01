"""Sentinel-2 L2A scene inventory from the Earth Search STAC catalogue.

Stores one row per catalogue item in raw.s2_items: when it was taken, its
footprint, tile cloud cover, and for each band the file location plus the
scale and offset needed to turn stored values into reflectance.
"""

import json
from collections.abc import Iterator
from datetime import UTC, datetime

import requests

from beech.db import apply_sql, connect

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
START = "2017-01-01"

# Bands used by the indices. NDVI: red and nir (10 m). NDMI: nir08 (B8A) and
# swir16 (B11), both 20 m. NDRE: nir08 and rededge1 (B05), both 20 m.
# scl is the scene classification layer used to mask cloud and shadow.
BANDS = ("red", "nir", "nir08", "rededge1", "swir16", "scl")


def search_items(
    session: requests.Session, aoi: dict, start: str, end: str, page_size: int = 100
) -> Iterator[dict]:
    """All items intersecting the area of interest, following 'next' links."""
    body = {
        "collections": [COLLECTION],
        "intersects": aoi,
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": page_size,
    }
    while True:
        r = session.post(STAC_SEARCH, json=body, timeout=120)
        r.raise_for_status()
        page = r.json()
        yield from page.get("features", [])
        nxt = next((ln for ln in page.get("links", []) if ln.get("rel") == "next"), None)
        if not nxt:
            return
        body = {**body, **nxt.get("body", {})}


def band_info(asset: dict) -> dict:
    rb = (asset.get("raster:bands") or [{}])[0]
    return {
        "href": asset["href"],
        "scale": rb.get("scale", 1),
        "offset": rb.get("offset", 0),
        "nodata": rb.get("nodata"),
        "resolution_m": rb.get("spatial_resolution"),
    }


def item_to_row(item: dict) -> dict:
    p = item["properties"]
    missing = [b for b in BANDS if b not in item["assets"]]
    if missing:
        raise ValueError(f"{item['id']} lacks bands {missing}")
    return {
        "item_id": item["id"],
        "collection": item.get("collection", COLLECTION),
        "acquired_at": p["datetime"],
        "platform": p.get("platform"),
        "mgrs_tile": p.get("grid:code"),
        "cloud_cover": p.get("eo:cloud_cover"),
        "processing_baseline": p.get("s2:processing_baseline"),
        "boa_offset_applied": p.get("earthsearch:boa_offset_applied"),
        "footprint": json.dumps(item["geometry"]),
        "bands": json.dumps({b: band_info(item["assets"][b]) for b in BANDS}),
        "properties": json.dumps(p),
    }


def main() -> None:
    apply_sql(["04_sentinel.sql"])
    end = datetime.now(UTC).date().isoformat()
    with connect() as conn:
        aoi = json.loads(conn.execute(
            "SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM analysis.study_area"
        ).fetchone()[0])
        run_id = conn.execute(
            "INSERT INTO qa.ingest_log (source, where_clause) VALUES (%s, %s) "
            "RETURNING run_id",
            (STAC_SEARCH, f"{COLLECTION} {START} to {end}, intersects study area"),
        ).fetchone()[0]

        rows, skipped = [], []
        for item in search_items(requests.Session(), aoi, START, end):
            try:
                rows.append({**item_to_row(item), "run_id": run_id})
            except ValueError as exc:
                skipped.append(str(exc))

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO raw.s2_items (item_id, collection, acquired_at, platform, "
                "mgrs_tile, cloud_cover, processing_baseline, boa_offset_applied, "
                "footprint, bands, properties, run_id) VALUES (%(item_id)s, "
                "%(collection)s, %(acquired_at)s, %(platform)s, %(mgrs_tile)s, "
                "%(cloud_cover)s, %(processing_baseline)s, %(boa_offset_applied)s, "
                "ST_SetSRID(ST_GeomFromGeoJSON(%(footprint)s), 4326), "
                "%(bands)s::jsonb, %(properties)s::jsonb, %(run_id)s) "
                "ON CONFLICT (item_id) DO UPDATE SET "
                "cloud_cover = EXCLUDED.cloud_cover, bands = EXCLUDED.bands, "
                "properties = EXCLUDED.properties, run_id = EXCLUDED.run_id",
                rows,
            )
        conn.execute(
            "UPDATE qa.ingest_log SET loaded_count = %s, finished_at = now() "
            "WHERE run_id = %s",
            (len(rows), run_id),
        )
        conn.commit()
    print(f"run {run_id}: {len(rows)} items stored, {len(skipped)} skipped")
    for s in skipped[:10]:
        print("  skipped:", s)


if __name__ == "__main__":
    main()
