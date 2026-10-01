"""Run QGIS model 02 (or 03) once per Sentinel-2 scene, in one QGIS session.

Called by src/beech/crown_indices.py (and ground_reference.py), which write
the scene list:
    python-qgis.bat qgis/scripts/run_model02.py <scenes.json> <out_dir> [model]

Any "extra" inputs in a scene entry (model 03's canopy cover) are passed on.

For each scene it writes <out_dir>/<item_id>.csv (one row per crown). Scenes
with a CSV already are skipped, so an interrupted run carries on where it
stopped. It also writes <out_dir>/scene_qa.csv: the raw red values over
vegetation in each scene, the evidence for which reflectance offset the
files really carry.
"""

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
from osgeo import gdal
from qgis.core import QgsApplication, QgsProcessingModelAlgorithm

ROOT = Path(__file__).resolve().parents[2]
MODEL_02 = ROOT / "qgis" / "models" / "02_crown_indices.model3"
BANDS = ("red", "nir", "nir08", "rededge1", "swir16", "scl")
QA_FIELDS = ["item_id", "veg_px", "red_p01", "red_p50", "nir_p50"]


def raw_levels(item_id: str, paths: dict) -> dict:
    """Percentiles of the stored red and NIR values over clear vegetation.

    With a +1000 offset in the file, no vegetation pixel could store less
    than about 1000; without it, the darkest vegetation stores close to 0.
    """
    red = gdal.Open(paths["red"])
    scl = gdal.Warp("", paths["scl"], format="MEM", outputBounds=_bounds(red),
                    width=red.RasterXSize, height=red.RasterYSize, resampleAlg="near")
    veg = scl.ReadAsArray() == 4
    r = red.ReadAsArray()[veg]
    n = gdal.Open(paths["nir"]).ReadAsArray()[veg]
    if not r.size:
        return {"item_id": item_id, "veg_px": 0}
    return {"item_id": item_id, "veg_px": int(r.size),
            "red_p01": float(np.percentile(r, 1)), "red_p50": float(np.median(r)),
            "nir_p50": float(np.median(n))}


def _bounds(ds):
    x0, dx, _, y0, _, dy = ds.GetGeoTransform()
    return (x0, y0 + dy * ds.RasterYSize, x0 + dx * ds.RasterXSize, y0)


def main() -> None:
    scenes = json.loads(Path(sys.argv[1]).read_text())
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    qgs = QgsApplication([], False)
    qgs.initQgis()
    sys.path.append(str(Path(QgsApplication.pkgDataPath()) / "python" / "plugins"))
    import processing
    from processing.core.Processing import Processing

    Processing.initialize()
    gdal.UseExceptions()
    model_path = Path(sys.argv[3]) if len(sys.argv) > 3 else MODEL_02
    model = QgsProcessingModelAlgorithm()
    if not model.fromFile(str(model_path)):
        raise SystemExit(f"could not read {model_path}")
    # The output parameter is named from the output label ("crown_readings").
    (dest,) = [d.name() for d in model.destinationParameterDefinitions()]

    qa_path = out_dir / "scene_qa.csv"
    done_qa = set()
    if qa_path.exists():
        with qa_path.open() as f:
            done_qa = {row["item_id"] for row in csv.DictReader(f)}
    with qa_path.open("a", newline="") as qa_file:
        qa = csv.DictWriter(qa_file, QA_FIELDS)
        if not done_qa:
            qa.writeheader()
        for i, s in enumerate(scenes, 1):
            out = out_dir / f"{s['item_id']}.csv"
            if s["item_id"] not in done_qa:
                qa.writerow(raw_levels(s["item_id"], s["bands"]))
                qa_file.flush()
            if out.exists():
                continue
            t = time.time()
            tmp = out.with_suffix(".part.csv")
            params = {b: s["bands"][b] for b in BANDS}
            params |= {"crowns": s["crowns"], "scale": s["scale"], "offset": s["offset"],
                       dest: str(tmp)} | s.get("extra", {})
            processing.run(model, params)
            tmp.replace(out)
            print(f"{i}/{len(scenes)} {s['item_id']} {time.time() - t:.0f}s", flush=True)
    qgs.exitQgis()


if __name__ == "__main__":
    main()
