"""Build QGIS model 01 (tree crowns from LIDAR) as code and save it.

Run with QGIS's own Python, no QGIS window needed:
    set QT_QPA_PLATFORM=offscreen
    "C:\\Program Files\\QGIS 4.0.3\\bin\\python-qgis.bat" qgis/scripts/build_model01.py

Writes qgis/models/01_tree_crowns.model3, which opens in the QGIS Graphical
Modeler (Processing Toolbox > Models > Open existing model) and runs headless
with qgis_process (src/beech/run_models.py).
"""

import sys
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProcessingModelAlgorithm,
    QgsProcessingModelChildAlgorithm,
    QgsProcessingModelOutput,
    QgsProcessingModelParameter,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProperty,
)
from qgis.core import (
    QgsProcessingModelChildParameterSource as S,
)
from qgis.PyQt.QtCore import QPointF

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "qgis" / "models" / "01_tree_crowns.model3"

DESCRIPTION = (
    "Draws a crown polygon for every large comparison tree in the council "
    "register. Canopy is LIDAR canopy height of at least the minimum height, "
    "with building footprints (plus 1 m) removed. Each tree gets the canopy "
    "inside its search circle (radius from the register crown width, 4 to "
    "12 m, plus 2 m) and inside its own Voronoi cell, built from every "
    "register tree so touching crowns are split between neighbours. Outputs "
    "crown area and canopy height statistics."
)
FIELDS = ["asset_id", "objectid", "species_group", "latin_name", "dbh_cm",
          "crown_width_m", "size_class", "site_type"]


def build() -> QgsProcessingModelAlgorithm:
    m = QgsProcessingModelAlgorithm("01 Tree crowns from LIDAR", "Bristol beech drought")
    m.setHelpContent({"ALG_DESC": DESCRIPTION})

    def param(defn, x, y):
        comp = QgsProcessingModelParameter(defn.name())
        comp.setPosition(QPointF(x, y))
        m.addModelParameter(defn, comp)

    param(QgsProcessingParameterRasterLayer("chm", "Canopy height model"), 160, 60)
    param(QgsProcessingParameterVectorLayer(
        "trees", "Register trees (all)", [Qgis.ProcessingSourceType.VectorPoint]), 570, 60)
    param(QgsProcessingParameterVectorLayer(
        "buildings", "OS buildings", [Qgis.ProcessingSourceType.VectorPolygon]), 1040, 60)
    param(QgsProcessingParameterNumber(
        "min_height", "Min canopy height (m)", Qgis.ProcessingNumberParameterType.Double, 5),
        -150, 760)

    P = S.fromModelParameter
    V = S.fromStaticValue

    def O(cid):
        return S.fromChildOutput(cid, "OUTPUT")

    def child(cid, alg, desc, x, y, **params):
        c = QgsProcessingModelChildAlgorithm(alg)
        c.setChildId(cid)
        c.setDescription(desc)
        c.setPosition(QPointF(x, y))
        for k, v in params.items():
            c.addParameterSources(k, [v])
        m.addChildAlgorithm(c)

    child("targets", "native:extractbyexpression", "1 Large comparison trees", 420, 200,
          INPUT=P("trees"),
          EXPRESSION=V('"in_comparison" AND ("dbh_cm" >= 40 OR "crown_width_m" >= 10)'))
    child("cells", "native:voronoipolygons", "3 Voronoi cells (all trees)", 720, 200,
          INPUT=P("trees"), BUFFER=V(5))
    child("circles", "native:buffer", "2 Search circle per tree", 420, 330,
          INPUT=O("targets"),
          DISTANCE=V(QgsProperty.fromExpression(
              'min(max(coalesce("crown_width_m" / 2, 8), 4), 12) + 2')),
          SEGMENTS=V(16), END_CAP_STYLE=V(0), JOIN_STYLE=V(0), MITER_LIMIT=V(2),
          DISSOLVE=V(False))
    child("zones_all", "native:intersection", "4 Circles x cells", 570, 460,
          INPUT=O("circles"), OVERLAY=O("cells"), OVERLAY_FIELDS=V(["asset_id"]),
          OVERLAY_FIELDS_PREFIX=V("v_"))
    child("zones", "native:extractbyexpression", "5 Keep own cell", 570, 590,
          INPUT=O("zones_all"), EXPRESSION=V('"asset_id" = "v_asset_id"'))
    child("chm_clip", "gdal:cliprasterbymasklayer", "6 Clip canopy to zones", 160, 620,
          INPUT=P("chm"), MASK=O("zones"), CROP_TO_CUTLINE=V(True),
          KEEP_RESOLUTION=V(True), NODATA=V(-9999))
    child("mask", "gdal:rastercalculator", "7 Canopy >= min height", 160, 760,
          INPUT_A=O("chm_clip"), BAND_A=V(1),
          FORMULA=S.fromExpression("'where(A >= ' || to_string(@min_height) || ', 1, 0)'"),
          NO_DATA=V(0), RTYPE=V(0), EXTENT_OPT=V(0))
    child("canopy", "gdal:polygonize", "8 Canopy to polygons", 160, 900,
          INPUT=O("mask"), BAND=V(1), FIELD=V("dn"), EIGHT_CONNECTEDNESS=V(False))
    child("bld_buf", "native:buffer", "9 Buildings + 1 m", 1040, 620,
          INPUT=P("buildings"), DISTANCE=V(1), SEGMENTS=V(4), END_CAP_STYLE=V(0),
          JOIN_STYLE=V(0), MITER_LIMIT=V(2), DISSOLVE=V(False))
    child("canopy_nb", "native:difference", "10 Remove roofs", 330, 1040,
          INPUT=O("canopy"), OVERLAY=O("bld_buf"))
    child("pieces", "native:intersection", "11 Canopy in tree zone", 570, 1180,
          INPUT=O("canopy_nb"), OVERLAY=O("zones"), INPUT_FIELDS=V(["dn"]),
          OVERLAY_FIELDS=V(FIELDS))
    child("crowns_raw", "native:dissolve", "12 One crown per tree", 570, 1310,
          INPUT=O("pieces"), FIELD=V(["asset_id"]))
    child("crowns_f", "native:retainfields", "13 Keep fields", 570, 1440,
          INPUT=O("crowns_raw"), FIELDS=V(FIELDS))
    # Heights come from the clipped canopy model: crowns lie inside the zones,
    # so the values are identical to the full model and the step is faster.
    child("crowns_z", "native:zonalstatisticsfb", "14 Height in crown", 570, 1570,
          INPUT=O("crowns_f"), INPUT_RASTER=O("chm_clip"), RASTER_BAND=V(1),
          COLUMN_PREFIX=V("chm_"), STATISTICS=V([0, 2, 6]))
    child("crowns", "native:fieldcalculator", "15 Crown area", 570, 1700,
          INPUT=O("crowns_z"), FIELD_NAME=V("crown_area_m2"), FIELD_TYPE=V(0),
          FIELD_LENGTH=V(10), FIELD_PRECISION=V(1), FORMULA=V("$area"))

    out = QgsProcessingModelOutput("tree_crowns", "Tree crowns")
    out.setChildId("crowns")
    out.setChildOutputName("OUTPUT")
    out.setPosition(QPointF(900, 1760))
    c = m.childAlgorithm("crowns")
    c.setModelOutputs({"tree_crowns": out})
    m.setChildAlgorithm(c)
    m.updateDestinationParameters()
    return m


def main() -> None:
    qgs = QgsApplication([], False)
    qgs.initQgis()
    sys.path.append(str(Path(QgsApplication.pkgDataPath()) / "python" / "plugins"))
    from processing.core.Processing import Processing

    Processing.initialize()
    m = build()
    ok, errors = m.validate()
    if not ok:
        raise SystemExit(f"model invalid: {errors}")
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    print("saved:", m.toFile(str(MODEL)), MODEL)
    qgs.exitQgis()


if __name__ == "__main__":
    main()
