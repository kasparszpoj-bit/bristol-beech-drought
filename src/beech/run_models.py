"""Run the QGIS Processing models headless with qgis_process.

Model 01 (qgis/models/01_tree_crowns.model3) draws a crown for every large
comparison tree. Inputs are exported from PostGIS to a GeoPackage so the run
is self-contained and repeatable; the output crowns are loaded back into
PostGIS as analysis.crowns and checked by sql/06_crowns.sql.
"""

import json
import subprocess
from pathlib import Path

from beech.db import PROJECT_ROOT, apply_sql
from beech.lidar import LIDAR_DIR, gdal_tool

MODEL_01 = PROJECT_ROOT / "qgis" / "models" / "01_tree_crowns.model3"
CROWN_DIR = PROJECT_ROOT / "data" / "crowns"
# One GeoPackage per input: qgis_process is a Windows batch file, and cmd
# would read the "|" in "file.gpkg|layername=x" as a pipe.
TREES_GPKG = CROWN_DIR / "trees.gpkg"
BUILDINGS_GPKG = CROWN_DIR / "buildings.gpkg"
CROWNS = CROWN_DIR / "crowns.gpkg"
PG = "PG:host=localhost port=5432 dbname=beech user=postgres"

TREES_SQL = (
    "SELECT objectid, asset_id, species_group, latin_name, dbh_cm, crown_width_m, "
    "size_class, site_type, in_comparison, geom FROM clean.trees WHERE in_study_area"
)
BUILDINGS_SQL = "SELECT fid AS building_id, geom FROM raw.os_buildings"


def qgis_process() -> str:
    for qgis in sorted(Path("C:/Program Files").glob("QGIS*"), reverse=True):
        candidate = qgis / "bin" / "qgis_process-qgis.bat"
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("qgis_process not found in a QGIS install")


def export_inputs() -> None:
    ogr = gdal_tool("ogr2ogr")
    CROWN_DIR.mkdir(parents=True, exist_ok=True)
    for path, name, sql in ((TREES_GPKG, "trees", TREES_SQL),
                            (BUILDINGS_GPKG, "buildings", BUILDINGS_SQL)):
        if path.exists():
            path.unlink()
        subprocess.run([ogr, "-f", "GPKG", str(path), PG, "-sql", sql,
                        "-nln", name, "-a_srs", "EPSG:27700"], check=True)


def model_args(chm: Path, trees: Path, buildings: Path, out: Path,
               min_height: float = 5) -> list[str]:
    return [
        "--json",
        "run", str(MODEL_01), "--",
        f"chm={chm}",
        f"trees={trees}",
        f"buildings={buildings}",
        f"min_height={min_height}",
        f"tree_crowns={out}",
    ]


def run_model_01() -> dict:
    if CROWNS.exists():
        CROWNS.unlink()
    result = subprocess.run(
        [qgis_process(), *model_args(LIDAR_DIR / "chm.tif", TREES_GPKG,
                                     BUILDINGS_GPKG, CROWNS)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout[result.stdout.index("{"):])


def load_crowns() -> None:
    subprocess.run(
        [gdal_tool("ogr2ogr"), "-f", "PostgreSQL", PG, str(CROWNS),
         "-nln", "analysis.crowns", "-overwrite",
         "-lco", "GEOMETRY_NAME=geom", "-lco", "FID=fid",
         "-nlt", "PROMOTE_TO_MULTI", "-a_srs", "EPSG:27700"],
        check=True,
    )


def main() -> None:
    export_inputs()
    print("inputs exported:", TREES_GPKG.name, BUILDINGS_GPKG.name)
    res = run_model_01()
    print("model 01 finished:", res.get("results", {}))
    load_crowns()
    # Reloading the crowns drops the views built on them; rebuild those too.
    print("applied:", apply_sql(["06_crowns.sql", "08_crown_obs.sql", "09_metrics.sql"]))


if __name__ == "__main__":
    main()
