"""Download a study-area window of each candidate Sentinel-2 scene.

For every scene in analysis.s2_candidates (May to October, 2018 to 2026,
nearly full study-area coverage, tile cloud under 60%), GDAL reads only the
study-area window of the six bands the indices need, straight from the
cloud-optimised GeoTIFFs on AWS (/vsicurl/), and writes compressed GeoTIFFs
to data/s2/<item_id>/<band>.tif. Stored values are kept as delivered; the
per-band scale and offset from raw.s2_items are applied when indices are
computed (QGIS model 02), so the 2022 processing offset is handled there.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from beech.db import PROJECT_ROOT, connect
from beech.lidar import gdal_tool
from beech.sentinel import BANDS

S2_DIR = PROJECT_ROOT / "data" / "s2"
FIRST_YEAR = 2018

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "AWS_NO_SIGN_REQUEST": "YES",
}


def translate_args(href: str, out: Path, bbox_bng: tuple[float, ...]) -> list[str]:
    """gdal_translate arguments for a British National Grid window of one band."""
    xmin, ymin, xmax, ymax = bbox_bng
    return [
        "-q",
        "-projwin", str(xmin), str(ymax), str(xmax), str(ymin),
        "-projwin_srs", "EPSG:27700",
        "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=2", "-co", "TILED=YES",
        f"/vsicurl/{href}",
        str(out),
    ]


def candidates(conn) -> list[tuple[str, dict]]:
    return conn.execute(
        "SELECT item_id, bands FROM analysis.s2_candidates "
        "WHERE year >= %s ORDER BY acquired_at",
        (FIRST_YEAR,),
    ).fetchall()


def fetch_band(tool: str, item_id: str, band: str, href: str, bbox) -> str:
    out = S2_DIR / item_id / f"{band}.tif"
    if out.exists() and out.stat().st_size > 10_000:
        return "kept"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.tif")
    r = subprocess.run([tool, *translate_args(href, tmp, bbox)], check=False,
                       env={**os.environ, **GDAL_ENV}, capture_output=True, text=True)
    if r.returncode != 0 or not tmp.exists():
        return f"failed: {r.stderr.strip()[:120]}"
    tmp.replace(out)
    return "downloaded"


def main(limit: int | None = None) -> None:
    tool = gdal_tool("gdal_translate")
    with connect() as conn:
        bbox = conn.execute(
            "SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) "
            "FROM analysis.study_area"
        ).fetchone()
        scenes = candidates(conn)
    if limit:
        scenes = scenes[:limit]
    jobs = [(item_id, b, bands[b]["href"]) for item_id, bands in scenes for b in BANDS]
    print(f"{len(scenes)} scenes, {len(jobs)} band windows")
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda j: fetch_band(tool, *j, bbox), jobs))
    summary: dict[str, int] = {}
    for r in results:
        summary[r.split(":")[0]] = summary.get(r.split(":")[0], 0) + 1
    print("band windows:", summary)
    for j, r in zip(jobs, results, strict=True):
        if r.startswith("failed"):
            print("  ", j[0], j[1], r)


if __name__ == "__main__":
    import sys

    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
