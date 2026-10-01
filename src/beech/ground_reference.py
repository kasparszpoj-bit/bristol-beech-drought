"""Each crown's local ground, for unmixing: QGIS model 03 over crown rings.

A crown's reading mixes canopy with the ground around it. The ground's own
readings come from a 15 m ring around the crown, keeping only clear pixels
with under 10% canopy on the LIDAR cover map (model 03). On the Downs that
is grass; along streets, pavement and road; so no single reference has to
stand in for every setting.

    beech-ground-reference            rings, model 03 for every scene, load
    beech-ground-reference --load     load only
"""

import json
import subprocess
import sys

from beech.canopy_cover import COVER_10M
from beech.crown_indices import SCENE_CRS, SCENES_JSON, obs_rows, python_qgis
from beech.db import PROJECT_ROOT, connect
from beech.lidar import gdal_tool
from beech.run_models import PG

GROUND_DIR = PROJECT_ROOT / "data" / "ground"
RINGS_UTM = GROUND_DIR / "rings_utm.gpkg"
SCENES = GROUND_DIR / "scenes.json"
OBS_DIR = GROUND_DIR / "obs"
RUNNER = PROJECT_ROOT / "qgis" / "scripts" / "run_model02.py"
MODEL_03 = PROJECT_ROOT / "qgis" / "models" / "03_ground_indices.model3"
RING_M = 15

RINGS_SQL = f"""
DROP TABLE IF EXISTS analysis.crown_rings CASCADE;
CREATE TABLE analysis.crown_rings AS
SELECT asset_id, ST_Multi(ST_Difference(ST_Buffer(geom, {RING_M}), geom)) AS geom
FROM analysis.crowns;
ALTER TABLE analysis.crown_rings ADD PRIMARY KEY (asset_id);
"""


def make_rings() -> None:
    GROUND_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute(RINGS_SQL)
        conn.commit()
    if RINGS_UTM.exists():
        RINGS_UTM.unlink()
    subprocess.run([gdal_tool("ogr2ogr"), "-f", "GPKG", str(RINGS_UTM), PG,
                    "-sql", "SELECT asset_id, geom FROM analysis.crown_rings",
                    "-s_srs", "EPSG:27700", "-t_srs", SCENE_CRS, "-nln", "crowns"],
                   check=True)


def write_scenes(item_ids: list[str] | None = None) -> None:
    scenes = json.loads(SCENES_JSON.read_text())
    if item_ids:
        scenes = [s for s in scenes if s["item_id"] in item_ids]
    for s in scenes:
        s["crowns"] = str(RINGS_UTM)
        s["extra"] = {"cover": str(COVER_10M)}
    SCENES.write_text(json.dumps(scenes, indent=1))


def run(out_dir=OBS_DIR) -> None:
    subprocess.run([python_qgis(), str(RUNNER), str(SCENES), str(out_dir), str(MODEL_03)],
                   check=True)


def load() -> int:
    files = [f for f in sorted(OBS_DIR.glob("*.csv"))
             if f.name != "scene_qa.csv" and not f.name.endswith(".part.csv")]
    n = 0
    with connect() as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS analysis.ground_obs CASCADE")
        cur.execute("CREATE TABLE analysis.ground_obs (LIKE analysis.crown_obs INCLUDING ALL)")
        with cur.copy("COPY analysis.ground_obs (item_id, asset_id, clear_px, clear_frac, "
                      "ndvi_px, ndvi, ndmi, ndre) FROM STDIN") as copy:
            for f in files:
                for row in obs_rows(f):
                    copy.write_row(row)
                    n += 1
        conn.commit()
    return n


def main() -> None:
    if "--load" not in sys.argv:
        make_rings()
        write_scenes()
        run()
    print("loaded", load(), "ground readings")


if __name__ == "__main__":
    main()
