"""The case study tree: its crown and satellite readings, kept private.

The garden tree is processed exactly like the council trees (QGIS models 01
and 02), but its location lives only in the private schema, and every file
written here goes under data/private/ (ignored by git). Nothing in this
module holds a coordinate.

    beech-case-study crown       draw its crown with model 01
    beech-case-study readings    run model 02 on that crown for every scene
    beech-case-study load        load the readings into private.case_study_obs
    beech-case-study ground      canopy share, ground ring and model 03, for
                                 unmixing exactly as for the council trees
"""

import json
import subprocess
import sys

from beech.crown_indices import SCENE_CRS, SCENES_JSON, obs_rows, python_qgis
from beech.db import PROJECT_ROOT, connect
from beech.lidar import LIDAR_DIR, gdal_tool
from beech.run_models import BUILDINGS_GPKG, PG, model_args, qgis_process

PRIVATE_DIR = PROJECT_ROOT / "data" / "private"
TREES = PRIVATE_DIR / "case_study_trees.gpkg"
CROWN = PRIVATE_DIR / "case_study_crown.gpkg"
CROWN_UTM = PRIVATE_DIR / "case_study_crown_utm.gpkg"
SCENES = PRIVATE_DIR / "case_study_scenes.json"
OBS_DIR = PRIVATE_DIR / "crown_obs"
RING_UTM = PRIVATE_DIR / "case_study_ring_utm.gpkg"
COVER_OUT = PRIVATE_DIR / "case_study_cover.gpkg"
GROUND_SCENES = PRIVATE_DIR / "case_study_ground_scenes.json"
GROUND_DIR = PRIVATE_DIR / "ground_obs"
RUNNER = PROJECT_ROOT / "qgis" / "scripts" / "run_model02.py"
ASSET_ID = "CASE_STUDY"

# The tree plus every register tree within 300 m, so its Voronoi cell is
# built from its real neighbours. Its trunk is well over 1 m across; the
# register has no crown width for it, so model 01 uses its default radius.
TREES_SQL = f"""
SELECT '{ASSET_ID}' AS asset_id, NULL::integer AS objectid, 'beech' AS species_group,
       species AS latin_name, 120::numeric AS dbh_cm, NULL::numeric AS crown_width_m,
       '4: 80 cm and over' AS size_class, 'private garden' AS site_type,
       true AS in_comparison, geom
FROM private.case_study_tree
UNION ALL
SELECT t.asset_id, t.objectid, t.species_group, t.latin_name, t.dbh_cm, t.crown_width_m,
       t.size_class, t.site_type, false AS in_comparison, t.geom
FROM clean.trees t, private.case_study_tree p
WHERE ST_DWithin(t.geom, p.geom, 300)
"""


def draw_crown() -> None:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    for f in (TREES, CROWN):
        if f.exists():
            f.unlink()
    ogr = gdal_tool("ogr2ogr")
    subprocess.run([ogr, "-f", "GPKG", str(TREES), PG, "-sql", TREES_SQL,
                    "-nln", "trees", "-a_srs", "EPSG:27700"], check=True)
    subprocess.run([qgis_process(), *model_args(LIDAR_DIR / "chm.tif", TREES,
                                                BUILDINGS_GPKG, CROWN)],
                   check=True, capture_output=True, text=True)
    subprocess.run([ogr, "-f", "PostgreSQL", PG, str(CROWN),
                    "-nln", "private.case_study_crown", "-overwrite",
                    "-lco", "GEOMETRY_NAME=geom", "-nlt", "PROMOTE_TO_MULTI",
                    "-a_srs", "EPSG:27700"], check=True)
    trim_crown()


# Model 01 keeps all canopy in the tree's zone, so the search circle can
# catch the edge of a neighbouring crown as a detached piece. Here that is a
# sliver of a tree across the road (checked with the owner, 30 September
# 2026), so only the piece at the tree is kept.
TRIM_SQL = """
UPDATE private.case_study_crown c
SET geom = ST_Multi((
    SELECT d.geom
    FROM ST_Dump(c.geom) d, private.case_study_tree t
    ORDER BY ST_Distance(d.geom, t.geom), ST_Area(d.geom) DESC
    LIMIT 1));
UPDATE private.case_study_crown SET crown_area_m2 = ST_Area(geom);
"""


def trim_crown() -> None:
    with connect() as conn:
        conn.execute(TRIM_SQL)
        conn.commit()


def run_readings() -> None:
    if CROWN_UTM.exists():
        CROWN_UTM.unlink()
    subprocess.run([gdal_tool("ogr2ogr"), "-f", "GPKG", str(CROWN_UTM), PG,
                    "-sql", "SELECT asset_id, geom FROM private.case_study_crown",
                    "-s_srs", "EPSG:27700", "-t_srs", SCENE_CRS, "-nln", "crowns"],
                   check=True)
    scenes = json.loads(SCENES_JSON.read_text())
    for s in scenes:
        s["crowns"] = str(CROWN_UTM)
    SCENES.write_text(json.dumps(scenes, indent=1))
    subprocess.run([python_qgis(), str(RUNNER), str(SCENES), str(OBS_DIR)], check=True)


def load() -> int:
    rows = [r for f in sorted(OBS_DIR.glob("*.csv"))
            if f.name != "scene_qa.csv" and not f.name.endswith(".part.csv")
            for r in obs_rows(f)]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS private.case_study_obs (
                item_id text PRIMARY KEY, asset_id text, clear_px real,
                clear_frac real, ndvi_px real, ndvi real, ndmi real, ndre real)""")
        cur.execute("TRUNCATE private.case_study_obs")
        cur.executemany("INSERT INTO private.case_study_obs VALUES "
                        "(%s, %s, %s, %s, %s, %s, %s, %s)", rows)
        conn.commit()
    return len(rows)


def ground() -> None:
    """Canopy share and local ground for the case study crown (models as public)."""
    from beech.canopy_cover import COVER_10M
    from beech.ground_reference import MODEL_03, RING_M

    if COVER_OUT.exists():
        COVER_OUT.unlink()
    subprocess.run([qgis_process(), "run", "native:zonalstatisticsfb", "--",
                    f"INPUT={CROWN_UTM}", f"INPUT_RASTER={COVER_10M}", "RASTER_BAND=1",
                    "COLUMN_PREFIX=cover_", "STATISTICS=2", f"OUTPUT={COVER_OUT}"],
                   check=True, capture_output=True, text=True)
    if RING_UTM.exists():
        RING_UTM.unlink()
    ring_sql = (f"SELECT asset_id, ST_Multi(ST_Difference(ST_Buffer(geom, {RING_M}), geom)) "
                "AS geom FROM private.case_study_crown")
    subprocess.run([gdal_tool("ogr2ogr"), "-f", "GPKG", str(RING_UTM), PG, "-sql", ring_sql,
                    "-s_srs", "EPSG:27700", "-t_srs", SCENE_CRS, "-nln", "crowns"], check=True)
    scenes = json.loads(SCENES_JSON.read_text())
    for sc in scenes:
        sc["crowns"] = str(RING_UTM)
        sc["extra"] = {"cover": str(COVER_10M)}
    GROUND_SCENES.write_text(json.dumps(scenes, indent=1))
    subprocess.run([python_qgis(), str(RUNNER), str(GROUND_SCENES), str(GROUND_DIR),
                    str(MODEL_03)], check=True)
    rows = [r for f in sorted(GROUND_DIR.glob("*.csv"))
            if f.name != "scene_qa.csv" and not f.name.endswith(".part.csv")
            for r in obs_rows(f)]
    share = subprocess.run([gdal_tool("ogrinfo"), "-q", "-sql",
                            "SELECT cover_mean FROM case_study_cover", str(COVER_OUT)],
                           check=True, capture_output=True, text=True).stdout
    canopy_share = float(share.split("cover_mean (Real) =")[1].split()[0])
    with connect() as conn, conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS private.case_study_ground "
                    "(LIKE private.case_study_obs INCLUDING ALL)")
        cur.execute("TRUNCATE private.case_study_ground")
        cur.executemany("INSERT INTO private.case_study_ground VALUES "
                        "(%s, %s, %s, %s, %s, %s, %s, %s)", rows)
        cur.execute("ALTER TABLE private.case_study_crown "
                    "ADD COLUMN IF NOT EXISTS canopy_share real")
        cur.execute("UPDATE private.case_study_crown SET canopy_share = %s", (canopy_share,))
        conn.commit()
    print(f"canopy share {canopy_share:.2f}; {len(rows)} ground readings")


def main() -> None:
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "crown":
        draw_crown()
        with connect() as conn:
            print(conn.execute(
                "SELECT asset_id, round(crown_area_m2::numeric), round(chm_max::numeric, 1) "
                "FROM private.case_study_crown").fetchall())
    elif step == "readings":
        run_readings()
    elif step == "load":
        print("loaded", load(), "readings")
    elif step == "ground":
        ground()
    else:
        raise SystemExit("usage: beech-case-study crown | readings | load | ground")


if __name__ == "__main__":
    main()
