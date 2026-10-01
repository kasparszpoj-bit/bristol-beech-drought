"""Grass reference plots: what open grass alone does each summer.

Most crowns are only a few 10 m pixels, so their readings include some of
the ground around them. On Clifton and Durdham Downs that ground is grass,
which browns in a dry summer. To separate the trees' signal from the
grass's, 30 m squares of open grass on the Downs are run through QGIS model
02 exactly like crowns.

    beech-grass-reference

A square qualifies if it lies among the Downs trees, at least 25 m from any
register tree, 20 m from any building and 15 m from any road, and the LIDAR
canopy height model has nothing over 1 m inside it (so no private or
unregistered trees or shrubs). Up to 20 are chosen by a fixed hash.
"""

import json
import subprocess

from beech.crown_indices import SCENE_CRS, SCENES_JSON, obs_rows, python_qgis
from beech.db import PROJECT_ROOT, connect
from beech.lidar import LIDAR_DIR, gdal_tool
from beech.run_models import PG, qgis_process

GRASS_DIR = PROJECT_ROOT / "data" / "grass_ref"
CANDIDATES = GRASS_DIR / "candidates.gpkg"
WITH_HEIGHT = GRASS_DIR / "candidates_chm.gpkg"
PLOTS_UTM = GRASS_DIR / "plots_utm.gpkg"
SCENES = GRASS_DIR / "scenes.json"
OBS_DIR = GRASS_DIR / "obs"
RUNNER = PROJECT_ROOT / "qgis" / "scripts" / "run_model02.py"
N_PLOTS = 20

CANDIDATES_SQL = """
WITH downs AS (
    SELECT ST_ConvexHull(ST_Collect(geom)) AS geom
    FROM clean.trees WHERE site_name = 'Clifton and Durdham Downs'
), cells AS (
    SELECT g.i, g.j, g.geom
    FROM downs d, ST_SquareGrid(30, d.geom) g
    WHERE ST_Within(g.geom, d.geom)
)
SELECT 'GRASS_' || c.i || '_' || c.j AS asset_id, c.geom
FROM cells c
WHERE NOT EXISTS (SELECT 1 FROM clean.trees t WHERE ST_DWithin(t.geom, c.geom, 25))
  AND NOT EXISTS (SELECT 1 FROM raw.os_buildings b WHERE ST_DWithin(b.geom, c.geom, 20))
  AND NOT EXISTS (SELECT 1 FROM raw.os_roads r WHERE ST_DWithin(r.geom, c.geom, 15))
"""


def build_plots() -> int:
    GRASS_DIR.mkdir(parents=True, exist_ok=True)
    for f in (CANDIDATES, WITH_HEIGHT):
        if f.exists():
            f.unlink()
    ogr = gdal_tool("ogr2ogr")
    subprocess.run([ogr, "-f", "GPKG", str(CANDIDATES), PG, "-sql", CANDIDATES_SQL,
                    "-nln", "candidates", "-a_srs", "EPSG:27700"], check=True)
    subprocess.run([qgis_process(), "run", "native:zonalstatisticsfb", "--",
                    f"INPUT={CANDIDATES}", f"INPUT_RASTER={LIDAR_DIR / 'chm.tif'}",
                    "RASTER_BAND=1", "COLUMN_PREFIX=chm_", "STATISTICS=6",
                    f"OUTPUT={WITH_HEIGHT}"],
                   check=True, capture_output=True, text=True)
    subprocess.run([ogr, "-f", "PostgreSQL", PG, str(WITH_HEIGHT),
                    "-nln", "analysis.grass_candidates", "-overwrite",
                    "-lco", "GEOMETRY_NAME=geom", "-a_srs", "EPSG:27700"], check=True)
    with connect() as conn:
        conn.execute("DROP TABLE IF EXISTS analysis.grass_plots CASCADE")
        conn.execute(f"""
            CREATE TABLE analysis.grass_plots AS
            SELECT asset_id, chm_max, geom FROM analysis.grass_candidates
            WHERE chm_max < 1
            ORDER BY md5(asset_id || 'beech-drought-2026') LIMIT {N_PLOTS}""")
        conn.execute("ALTER TABLE analysis.grass_plots ADD PRIMARY KEY (asset_id)")
        n = conn.execute("SELECT count(*) FROM analysis.grass_plots").fetchone()[0]
        conn.commit()
    return n


def run_readings() -> None:
    if PLOTS_UTM.exists():
        PLOTS_UTM.unlink()
    subprocess.run([gdal_tool("ogr2ogr"), "-f", "GPKG", str(PLOTS_UTM), PG,
                    "-sql", "SELECT asset_id, geom FROM analysis.grass_plots",
                    "-s_srs", "EPSG:27700", "-t_srs", SCENE_CRS, "-nln", "crowns"],
                   check=True)
    scenes = json.loads(SCENES_JSON.read_text())
    for s in scenes:
        s["crowns"] = str(PLOTS_UTM)
    SCENES.write_text(json.dumps(scenes, indent=1))
    subprocess.run([python_qgis(), str(RUNNER), str(SCENES), str(OBS_DIR)], check=True)


def load() -> int:
    rows = [r for f in sorted(OBS_DIR.glob("*.csv"))
            if f.name != "scene_qa.csv" and not f.name.endswith(".part.csv")
            for r in obs_rows(f)]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS analysis.grass_obs CASCADE")
        cur.execute("CREATE TABLE analysis.grass_obs (LIKE analysis.crown_obs INCLUDING ALL)")
        cur.executemany("INSERT INTO analysis.grass_obs VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        rows)
        conn.commit()
    return len(rows)


def main() -> None:
    print("grass plots:", build_plots())
    run_readings()
    print("loaded", load(), "grass readings")


if __name__ == "__main__":
    main()
