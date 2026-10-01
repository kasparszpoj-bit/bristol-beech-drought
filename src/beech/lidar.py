"""Download Environment Agency LIDAR (1 m) for the squares holding large trees.

Two layers from the EA LIDAR Composite (Open Government Licence), via WCS:
  dtm  Digital Terrain Model: the bare ground
  dsm  First-return Digital Surface Model: the top of whatever the laser hit
       first, which over a tree is its canopy
Canopy height is dsm minus dtm, computed later in QGIS (model 01).

Only 1 km squares containing large comparison trees are fetched (trunk of
40 cm or more, or crown of 10 m or more), plus any neighbouring square a
tree sits within 20 m of, so no crown is cut off at a tile edge. Tiles land
in data/lidar/<layer>/, which is never committed. A virtual mosaic (.vrt) is
built for each layer with GDAL from the QGIS install.
"""

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from beech.db import PROJECT_ROOT, connect

WCS = "https://environment.data.gov.uk/spatialdata"
LAYERS = {
    "dtm": (
        f"{WCS}/lidar-composite-digital-terrain-model-dtm-1m/wcs",
        "13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m",
    ),
    "dsm": (
        f"{WCS}/lidar-composite-digital-surface-model-first-return-dsm-1m/wcs",
        "df4e3ec3-315e-48aa-aaaf-b5ae74d7b2bb__Lidar_Composite_Elevation_FZ_DSM_1m",
    ),
}
LIDAR_DIR = PROJECT_ROOT / "data" / "lidar"
TILE_M = 1000
EDGE_BUFFER_M = 20

# The large trees the crowns are needed for; the private case study tree is
# added from the private schema if it exists, so its location never appears
# in this repo.
TILES_SQL = f"""
WITH pts AS (
    SELECT geom FROM clean.trees
    WHERE in_comparison AND in_study_area
      AND (dbh_cm >= 40 OR crown_width_m >= 10)
    {{private}}
)
SELECT DISTINCT
    ({TILE_M} * floor(x / {TILE_M}))::int AS e0,
    ({TILE_M} * floor(y / {TILE_M}))::int AS n0
FROM pts
CROSS JOIN LATERAL (VALUES
    (ST_X(geom) - {EDGE_BUFFER_M}, ST_Y(geom) - {EDGE_BUFFER_M}),
    (ST_X(geom) + {EDGE_BUFFER_M}, ST_Y(geom) - {EDGE_BUFFER_M}),
    (ST_X(geom) - {EDGE_BUFFER_M}, ST_Y(geom) + {EDGE_BUFFER_M}),
    (ST_X(geom) + {EDGE_BUFFER_M}, ST_Y(geom) + {EDGE_BUFFER_M})
) AS c(x, y)
ORDER BY e0, n0
"""


def tile_path(layer: str, e0: int, n0: int) -> Path:
    return LIDAR_DIR / layer / f"{layer}_{e0}_{n0}.tif"


def coverage_url(layer: str, e0: int, n0: int) -> str:
    base, coverage = LAYERS[layer]
    return (
        f"{base}?service=WCS&version=2.0.1&request=GetCoverage"
        f"&CoverageId={coverage}&format=image/tiff"
        f"&subset=E({e0},{e0 + TILE_M})&subset=N({n0},{n0 + TILE_M})"
    )


def tiles_needed(conn) -> list[tuple[int, int]]:
    has_private = conn.execute(
        "SELECT to_regclass('private.case_study_tree') IS NOT NULL"
    ).fetchone()[0]
    extra = "UNION ALL SELECT geom FROM private.case_study_tree" if has_private else ""
    return conn.execute(TILES_SQL.format(private=extra)).fetchall()


def fetch(session: requests.Session, layer: str, e0: int, n0: int) -> str:
    out = tile_path(layer, e0, n0)
    if out.exists() and out.stat().st_size > 1_000_000:
        return "kept"
    for _attempt in range(3):
        r = session.get(coverage_url(layer, e0, n0), timeout=180)
        if r.ok and r.headers.get("content-type", "").startswith("image/tiff"):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
            return "downloaded"
    return f"failed ({r.status_code})"


def gdal_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for qgis in sorted(Path("C:/Program Files").glob("QGIS*"), reverse=True):
        candidate = qgis / "bin" / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    return None


def build_vrt(layer: str) -> Path | None:
    tool = gdal_tool("gdalbuildvrt")
    tiles = sorted((LIDAR_DIR / layer).glob("*.tif"))
    if not tool or not tiles:
        return None
    vrt = LIDAR_DIR / f"{layer}.vrt"
    listing = LIDAR_DIR / f"{layer}_tiles.txt"
    listing.write_text("\n".join(str(t) for t in tiles), encoding="utf-8")
    subprocess.run(
        [tool, "-overwrite", "-input_file_list", str(listing), str(vrt)],
        check=True, capture_output=True,
    )
    return vrt


def main() -> None:
    with connect() as conn:
        tiles = tiles_needed(conn)
    print(f"{len(tiles)} one-kilometre squares needed, 2 layers each")

    session = requests.Session()
    jobs = [(layer, e0, n0) for layer in LAYERS for e0, n0 in tiles]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda j: fetch(session, *j), jobs))

    summary: dict[str, int] = {}
    for r in results:
        key = r.split(" ")[0]
        summary[key] = summary.get(key, 0) + 1
    print("tiles:", summary)
    failed = [j for j, r in zip(jobs, results, strict=True) if r.startswith("failed")]
    for f in failed[:10]:
        print("  failed:", f)

    for layer in LAYERS:
        print(layer, "mosaic:", build_vrt(layer))


if __name__ == "__main__":
    main()
