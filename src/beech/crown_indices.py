"""Satellite readings per crown: run QGIS model 02 over every scene.

1. Export the crowns, reprojected to the scenes' CRS (UTM zone 30N), so
   zonal statistics work on the images' own pixel grid.
2. Write data/s2/scenes.json: band paths, scale and offset for each scene.
3. Run qgis/scripts/run_model02.py with QGIS's Python: one CSV per scene.
4. Load the CSVs into analysis.crown_obs (sql/08_crown_obs.sql).

    beech-crown-indices            all four steps (resumes if interrupted)
    beech-crown-indices --load     step 4 only

The reflectance offset. The catalogue gives an offset of -0.1 for every
scene from processing baseline 04.00 on (June 2018 onwards in this archive).
The stored values say otherwise: the darkest vegetation stores values near
0 in every scene and the median red over vegetation is about 450 before and
after the change, so the offset has already been removed from these files.
Applying the catalogue offset would lower every later reflectance by 0.1.
The offset used is therefore 0 for every scene; the evidence is recorded per
scene in analysis.s2_scene_qa and checked in qa.s2_offset_evidence.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

from beech.db import PROJECT_ROOT, apply_sql, connect
from beech.lidar import gdal_tool
from beech.run_models import PG
from beech.s2_download import FIRST_YEAR, S2_DIR
from beech.sentinel import BANDS

CROWN_DIR = PROJECT_ROOT / "data" / "crowns"
CROWNS_UTM = CROWN_DIR / "crowns_utm.gpkg"
SCENES_JSON = S2_DIR / "scenes.json"
OBS_DIR = PROJECT_ROOT / "data" / "crown_obs"
RUNNER = PROJECT_ROOT / "qgis" / "scripts" / "run_model02.py"
SCENE_CRS = "EPSG:32630"
OFFSET_IN_FILES = 0.0
REFLECTANCE_BANDS = ("red", "nir", "nir08", "rededge1", "swir16")


def python_qgis() -> str:
    for qgis in sorted(Path("C:/Program Files").glob("QGIS*"), reverse=True):
        candidate = qgis / "bin" / "python-qgis.bat"
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("python-qgis.bat not found in a QGIS install")


def export_crowns() -> None:
    CROWN_DIR.mkdir(parents=True, exist_ok=True)
    if CROWNS_UTM.exists():
        CROWNS_UTM.unlink()
    subprocess.run(
        [gdal_tool("ogr2ogr"), "-f", "GPKG", str(CROWNS_UTM), PG,
         "-sql", "SELECT asset_id, geom FROM analysis.crowns",
         "-nln", "crowns", "-s_srs", "EPSG:27700", "-t_srs", SCENE_CRS],
        check=True,
    )


def scene_entry(item_id: str, bands: dict, crowns: Path = CROWNS_UTM) -> dict:
    """Model 02 inputs for one scene. All reflectance bands must share a scale."""
    scales = {bands[b]["scale"] for b in REFLECTANCE_BANDS}
    if len(scales) != 1:
        raise ValueError(f"{item_id}: bands have different scales {scales}")
    return {
        "item_id": item_id,
        "bands": {b: str(S2_DIR / item_id / f"{b}.tif") for b in BANDS},
        "crowns": str(crowns),
        "scale": scales.pop(),
        "offset": OFFSET_IN_FILES,
        "catalogue_offset": bands["red"]["offset"],
    }


def write_scenes() -> int:
    with connect() as conn:
        rows = conn.execute(
            "SELECT item_id, bands FROM analysis.s2_candidates "
            "WHERE year >= %s ORDER BY acquired_at",
            (FIRST_YEAR,),
        ).fetchall()
    scenes = [scene_entry(i, b) for i, b in rows]
    missing = [s["item_id"] for s in scenes
               if not all(Path(p).exists() for p in s["bands"].values())]
    if missing:
        raise FileNotFoundError(f"band files missing for {len(missing)} scenes: {missing[:3]}")
    SCENES_JSON.write_text(json.dumps(scenes, indent=1))
    return len(scenes)


def run_model_02() -> None:
    subprocess.run([python_qgis(), str(RUNNER), str(SCENES_JSON), str(OBS_DIR)], check=True)


def _num(v: str) -> float | None:
    return float(v) if v not in ("", "NULL", None) else None


def obs_rows(path: Path):
    """Rows for analysis.crown_obs from one scene's CSV."""
    item_id = path.stem
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            yield (item_id, r["asset_id"], _num(r["clear_count"]), _num(r["clear_mean"]),
                   _num(r["ndvi_count"]), _num(r["ndvi_mean"]), _num(r["ndmi_mean"]),
                   _num(r["ndre_mean"]))


def load() -> tuple[int, int]:
    apply_sql(["08_crown_obs.sql"])
    files = sorted(p for p in OBS_DIR.glob("*.csv")
                   if p.name != "scene_qa.csv" and not p.name.endswith(".part.csv"))
    n = 0
    with connect() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE analysis.crown_obs, analysis.s2_scene_qa")
        with cur.copy("COPY analysis.crown_obs (item_id, asset_id, clear_px, clear_frac, "
                      "ndvi_px, ndvi, ndmi, ndre) FROM STDIN") as copy:
            for f in files:
                for row in obs_rows(f):
                    copy.write_row(row)
                    n += 1
        qa = OBS_DIR / "scene_qa.csv"
        if qa.exists():
            with qa.open(newline="") as fh, cur.copy(
                    "COPY analysis.s2_scene_qa (item_id, veg_px, red_p01, red_p50, nir_p50) "
                    "FROM STDIN") as copy:
                for r in csv.DictReader(fh):
                    copy.write_row([r["item_id"], int(r["veg_px"]), _num(r.get("red_p01")),
                                    _num(r.get("red_p50")), _num(r.get("nir_p50"))])
        conn.commit()
    return len(files), n


def main() -> None:
    if "--load" not in sys.argv:
        export_crowns()
        print("crowns exported:", CROWNS_UTM)
        print("scenes:", write_scenes())
        run_model_02()
    scenes, rows = load()
    print(f"loaded {rows} crown readings from {scenes} scenes")


if __name__ == "__main__":
    main()
