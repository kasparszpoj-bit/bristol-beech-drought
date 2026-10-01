"""Load Ordnance Survey OpenMap Local buildings and roads into PostGIS.

Source: OS OpenMap Local, ST 100 km square, ESRI Shapefile (Open Government
Licence), from the OS Data Hub downloads API. Buildings are used to remove
roofs from the LIDAR canopy height model before crowns are drawn; roads are
used for the fall zone screening in chapter 2. Both are clipped to the study
area bounding box on load with ogr2ogr from the QGIS install.
"""

import subprocess
import zipfile
from pathlib import Path

import requests

from beech.db import PROJECT_ROOT, connect
from beech.lidar import gdal_tool

URL = (
    "https://api.os.uk/downloads/v1/products/OpenMapLocal/downloads"
    "?area=ST&format=ESRI%C2%AE+Shapefile&redirect"
)
OS_DIR = PROJECT_ROOT / "data" / "os"
ZIP = OS_DIR / "opmplc_essh_st.zip"
LAYERS = {"Building": "raw.os_buildings", "Road": "raw.os_roads"}
PG = "PG:host=localhost port=5432 dbname=beech user=postgres"


def download() -> Path:
    if not ZIP.exists():
        OS_DIR.mkdir(parents=True, exist_ok=True)
        with requests.get(URL, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(ZIP, "wb") as f:
                f.writelines(r.iter_content(1 << 20))
    return ZIP


def extract(layer: str) -> Path:
    """Extract one layer's shapefile parts; returns the .shp path."""
    with zipfile.ZipFile(ZIP) as z:
        parts = [n for n in z.namelist() if Path(n).stem == f"ST_{layer}"]
        if not parts:
            raise FileNotFoundError(f"ST_{layer} not in {ZIP.name}")
        for n in parts:
            target = OS_DIR / Path(n).name
            if not target.exists():
                target.write_bytes(z.read(n))
    return OS_DIR / f"ST_{layer}.shp"


def ogr2ogr_args(shp: Path, table: str, bbox: tuple[float, ...]) -> list[str]:
    return [
        "-f", "PostgreSQL", PG, str(shp),
        "-nln", table,
        "-overwrite",
        "-lco", "GEOMETRY_NAME=geom",
        "-lco", "FID=fid",
        "-nlt", "PROMOTE_TO_MULTI",
        "-a_srs", "EPSG:27700",
        "-spat", *(str(v) for v in bbox),
    ]


def main() -> None:
    download()
    tool = gdal_tool("ogr2ogr")
    if not tool:
        raise SystemExit("ogr2ogr not found (looked on PATH and in the QGIS install)")
    with connect() as conn:
        bbox = conn.execute(
            "SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) "
            "FROM analysis.study_area"
        ).fetchone()
        for layer, table in LAYERS.items():
            shp = extract(layer)
            subprocess.run([tool, *ogr2ogr_args(shp, table, bbox)], check=True)
            n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            conn.execute(
                "INSERT INTO qa.ingest_log (source, where_clause, loaded_count, "
                "finished_at) VALUES (%s, %s, %s, now())",
                (URL, f"ST_{layer}, study area bbox", n),
            )
            print(f"{table}: {n} features")
        conn.commit()


if __name__ == "__main__":
    main()
