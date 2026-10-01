"""Build QGIS model 02 (satellite indices per crown) as code and save it.

Run with QGIS's own Python, no QGIS window needed:
    "C:\\Program Files\\QGIS 4.0.3\\bin\\python-qgis.bat" qgis/scripts/build_model02.py

Writes qgis/models/02_crown_indices.model3, which opens in the QGIS Graphical
Modeler and is run once per Sentinel-2 scene by qgis/scripts/run_model02.py.
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
)
from qgis.core import (
    QgsProcessingModelChildParameterSource as S,
)
from qgis.PyQt.QtCore import QPointF

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "qgis" / "models"

DESCRIPTION = (
    "Satellite readings for every tree crown from one Sentinel-2 scene. "
    "Cloud, cloud shadow and snow are masked pixel by pixel with the scene "
    "classification layer (kept: vegetation, bare ground, unclassified). "
    "Three indices are computed on the 10 m grid from reflectance (stored "
    "value x scale + offset): NDVI greenness (B08, B04), NDMI canopy "
    "moisture (B8A, B11) and NDRE red edge (B8A, B05). Each is averaged over "
    "every crown, with the number of clear pixels and the clear share."
)
OUTPUT_FIELDS = ["asset_id", "clear_count", "clear_mean", "ndvi_count", "ndvi_mean",
                 "ndmi_mean", "ndre_mean"]


def reflectance(letter: str) -> str:
    """QGIS expression text for one band's reflectance, from model variables."""
    return f"(\"{letter}@1\" * ' || to_string(@scale) || ' + ' || to_string(@offset) || ')"


def index_expression(first: str, second: str) -> str:
    """A QGIS expression that builds the raster calculator formula.

    (first - second) / (first + second), divided by the clear mask (layer C):
    dividing by 0 makes cloudy pixels no data. Built from the scale and offset
    parameters, so the formula is correct for any processing version.
    """
    a, b = reflectance(first), reflectance(second)
    return f"'(({a} - {b}) / ({a} + {b})) / \"C@1\"'"


GROUND_DESCRIPTION = (
    "Satellite readings for the ground around every tree crown, from one "
    "Sentinel-2 scene: model 02's chain run over a ring around each crown, "
    "keeping only clear pixels with under 10% canopy on the LIDAR cover map. "
    "Used to remove the ground's share from mixed crown pixels."
)


def build(ground: bool = False) -> QgsProcessingModelAlgorithm:
    name = "03 Satellite indices of ground around crowns" if ground else         "02 Satellite indices per crown"
    m = QgsProcessingModelAlgorithm(name, "Bristol beech drought")
    m.setHelpContent({"ALG_DESC": GROUND_DESCRIPTION if ground else DESCRIPTION})

    def param(defn, x, y):
        comp = QgsProcessingModelParameter(defn.name())
        comp.setPosition(QPointF(x, y))
        m.addModelParameter(defn, comp)

    bands = [("red", "B04 red"), ("nir", "B08 near infrared"),
             ("rededge1", "B05 red edge"), ("nir08", "B8A narrow NIR"),
             ("swir16", "B11 shortwave IR"), ("scl", "Scene classes")]
    for i, (name, label) in enumerate(bands):
        param(QgsProcessingParameterRasterLayer(name, label), 150 + i * 280, 60)
    param(QgsProcessingParameterVectorLayer(
        "crowns", "Rings around crowns" if ground else "Tree crowns",
        [Qgis.ProcessingSourceType.VectorPolygon]), 1960, 60)
    if ground:
        param(QgsProcessingParameterRasterLayer("cover", "Canopy cover (10 m)"), 1550, 0)
    param(QgsProcessingParameterNumber(
        "scale", "Reflectance scale", Qgis.ProcessingNumberParameterType.Double, 0.0001),
        -170, 330)
    param(QgsProcessingParameterNumber(
        "offset", "Reflectance offset", Qgis.ProcessingNumberParameterType.Double, 0),
        -170, 440)

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
            c.addParameterSources(k, v if isinstance(v, list) else [v])
        m.addChildAlgorithm(c)

    # Every index is written on the red band's 10 m grid; 20 m bands are
    # read by nearest neighbour, so no values are invented.
    grid = {"EXTENT": P("red"), "CELL_SIZE": V(10), "CRS": P("red")}

    clear = '("A@1" = 4) OR ("A@1" = 5) OR ("A@1" = 7)'
    if ground:
        child("clear", "native:modelerrastercalc", "1 Clear ground (1) or not (0)", 1550, 220,
              LAYERS=[P("scl"), P("cover")],
              EXPRESSION=V(f'({clear}) AND ("B@1" < 0.1)'), **grid)
    else:
        child("clear", "native:modelerrastercalc", "1 Clear (1) or cloud (0)", 1550, 220,
              LAYERS=[P("scl")], EXPRESSION=V(clear), **grid)
    child("ndvi", "native:modelerrastercalc", "2 NDVI, greenness", 290, 400,
          LAYERS=[P("red"), P("nir"), O("clear")],
          EXPRESSION=S.fromExpression(index_expression("B", "A")), **grid)
    child("ndmi", "native:modelerrastercalc", "3 NDMI, canopy moisture", 1150, 400,
          LAYERS=[P("nir08"), P("swir16"), O("clear")],
          EXPRESSION=S.fromExpression(index_expression("A", "B")), **grid)
    child("ndre", "native:modelerrastercalc", "4 NDRE, red edge", 720, 400,
          LAYERS=[P("nir08"), P("rededge1"), O("clear")],
          EXPRESSION=S.fromExpression(index_expression("A", "B")), **grid)

    def zonal(cid, desc, x, y, source, raster, prefix, stats):
        child(cid, "native:zonalstatisticsfb", desc, x, y,
              INPUT=source, INPUT_RASTER=O(raster), RASTER_BAND=V(1),
              COLUMN_PREFIX=V(prefix), STATISTICS=V(stats))

    # count (0) and mean (2): for the clear mask, all pixels in the crown and
    # the clear share; for NDVI, the clear pixels and their mean.
    zonal("z_clear", "5 Clear share per crown", 1960, 400, P("crowns"), "clear", "clear_", [0, 2])
    zonal("z_ndvi", "6 NDVI per crown", 1550, 580, O("z_clear"), "ndvi", "ndvi_", [0, 2])
    zonal("z_ndmi", "7 NDMI per crown", 1550, 710, O("z_ndvi"), "ndmi", "ndmi_", [2])
    zonal("z_ndre", "8 NDRE per crown", 1550, 840, O("z_ndmi"), "ndre", "ndre_", [2])
    child("obs", "native:retainfields", "9 Keep readings", 1550, 970,
          INPUT=O("z_ndre"), FIELDS=V(OUTPUT_FIELDS))

    out = QgsProcessingModelOutput("crown_obs", "Crown readings")
    out.setChildId("obs")
    out.setChildOutputName("OUTPUT")
    out.setPosition(QPointF(1900, 1050))
    c = m.childAlgorithm("obs")
    c.setModelOutputs({"crown_obs": out})
    m.setChildAlgorithm(c)
    m.updateDestinationParameters()
    return m


def main() -> None:
    qgs = QgsApplication([], False)
    qgs.initQgis()
    sys.path.append(str(Path(QgsApplication.pkgDataPath()) / "python" / "plugins"))
    from processing.core.Processing import Processing

    Processing.initialize()
    MODELS.mkdir(parents=True, exist_ok=True)
    for ground, file in ((False, "02_crown_indices.model3"), (True, "03_ground_indices.model3")):
        m = build(ground)
        ok, errors = m.validate()
        if not ok:
            raise SystemExit(f"model invalid: {errors}")
        print("saved:", m.toFile(str(MODELS / file)), file)
    qgs.exitQgis()


if __name__ == "__main__":
    main()
