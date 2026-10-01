"""Canopy cover on the satellite's own 10 m grid, from 1 m LIDAR.

Most crowns are only a few 10 m pixels, so a crown's reading mixes canopy
with whatever surrounds it (grass, pavement, roofs). To separate the two,
this measures how much of each pixel really is canopy:

1. Canopy at 1 m: canopy height of 5 m or more, with building footprints
   burnt out (as in model 01).
2. Averaged onto the Sentinel-2 grid (UTM zone 30N, 10 m, the same pixel
   edges as the images), giving the canopy fraction of every pixel.
3. Zonal mean over every crown, with the same pixel weighting model 02 uses:
   the canopy share of that crown's reading (analysis.crown_cover).

    beech-canopy-cover
"""

import json
import subprocess
from pathlib import Path

from beech.crown_indices import CROWNS_UTM, SCENE_CRS
from beech.db import PROJECT_ROOT, connect
from beech.lidar import LIDAR_DIR, gdal_tool
from beech.run_models import BUILDINGS_GPKG, PG, qgis_process
from beech.s2_download import S2_DIR

COVER_DIR = PROJECT_ROOT / "data" / "cover"
CANOPY_1M = COVER_DIR / "canopy_1m.tif"
COVER_10M = COVER_DIR / "cover_10m.tif"
CROWN_COVER = COVER_DIR / "crown_cover.gpkg"
MIN_HEIGHT = 5


def grid_of(path: Path) -> tuple[tuple[float, ...], int, int]:
    info = json.loads(subprocess.run([gdal_tool("gdalinfo"), "-json", str(path)],
                                     check=True, capture_output=True, text=True).stdout)
    w, h = info["size"]
    return tuple(info["geoTransform"]), w, h


def s2_grid(reference: Path) -> list[str]:
    """gdalwarp -te/-tr arguments that reproduce a Sentinel-2 window's grid."""
    (x0, dx, _, y0, _, dy), w, h = grid_of(reference)
    te = [str(x0), str(y0 + dy * h), str(x0 + dx * w), str(y0)]
    return ["-te", *te, "-tr", str(dx), str(-dy)]


def reference_band() -> Path:
    return next(S2_DIR.glob("*/red.tif"))


def check_grids_match() -> int:
    """Every downloaded red band must share one grid, or the cover is misaligned."""
    grids = {grid_of(f) for f in S2_DIR.glob("*/red.tif")}
    if len(grids) != 1:
        raise RuntimeError(f"{len(grids)} different Sentinel-2 grids")
    return len(grids)


def build_cover() -> None:
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    for f in (CANOPY_1M, COVER_10M):
        if f.exists():
            f.unlink()
    # 1 where canopy height is at least MIN_HEIGHT, else 0 (heights start at 0,
    # clear of the -9999 no data value); missing stays missing.
    # (reclassify, because this GDAL build has no expression engine for calc)
    subprocess.run([gdal_tool("gdal"), "raster", "reclassify", "-q",
                    "-i", str(LIDAR_DIR / "chm.tif"), "-o", str(CANOPY_1M),
                    "-m", f"[0,{MIN_HEIGHT})=0; [{MIN_HEIGHT},inf]=1; NO_DATA=NO_DATA",
                    "--ot", "Int16", "--co", "COMPRESS=DEFLATE"], check=True)
    # Roofs stand above 5 m too: burn building footprints out as not canopy.
    subprocess.run([gdal_tool("gdal_rasterize"), "-q", "-burn", "0", "-at",
                    str(BUILDINGS_GPKG), str(CANOPY_1M)], check=True)
    grid = s2_grid(reference_band())
    subprocess.run([gdal_tool("gdalwarp"), "-q", "-t_srs", SCENE_CRS, *grid,
                    "-r", "average", "-ot", "Float32", "-co", "COMPRESS=DEFLATE",
                    str(CANOPY_1M), str(COVER_10M)], check=True)


def crown_cover() -> None:
    if CROWN_COVER.exists():
        CROWN_COVER.unlink()
    subprocess.run([qgis_process(), "run", "native:zonalstatisticsfb", "--",
                    f"INPUT={CROWNS_UTM}", f"INPUT_RASTER={COVER_10M}", "RASTER_BAND=1",
                    "COLUMN_PREFIX=cover_", "STATISTICS=2", f"OUTPUT={CROWN_COVER}"],
                   check=True, capture_output=True, text=True)
    subprocess.run([gdal_tool("ogr2ogr"), "-f", "PostgreSQL", PG, str(CROWN_COVER),
                    "-nln", "analysis.crown_cover", "-overwrite", "-lco", "GEOMETRY_NAME=geom",
                    # qgis_process names the output layer after the file.
                    "-sql", "SELECT asset_id, cover_mean AS canopy_share FROM crown_cover"],
                   check=True)


def main() -> None:
    print("Sentinel-2 grids:", check_grids_match())
    build_cover()
    print("cover built:", COVER_10M)
    crown_cover()
    with connect() as conn:
        print(conn.execute(
            "SELECT count(*), round(avg(canopy_share)::numeric, 2), "
            "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY canopy_share)::numeric, 2) "
            "FROM analysis.crown_cover").fetchone())


if __name__ == "__main__":
    main()
