"""Render the Power BI tree explorer's basemap from PostGIS, with QGIS.

    "C:\\Program Files\\QGIS 4.0.3\\bin\\python-qgis.bat" qgis/scripts/render_basemap.py

Power BI's map visuals need a work or school sign-in, so the tree explorer is
a scatter chart of longitude against latitude with this image as its plot
background. The image is drawn in WGS84 (EPSG:4326) for exactly the axis
range the chart uses (EXTENT, shared with src/beech/powerbi_report.py), so a
point at a given longitude and latitude lands on the right street.

Writes outputs/figures/powerbi_basemap.png. Contains OS data and the ONS
Bristol boundary; no tree locations.
"""

import sys
from pathlib import Path

from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsRectangle
from qgis.PyQt.QtGui import QColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_figures as rf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "figures" / "powerbi_basemap.png"
# lon_min, lon_max, lat_min, lat_max: keep in step with powerbi_report.MAP_EXTENT
EXTENT = (-2.7258, -2.4862, 51.4015, 51.5163)
WIDTH = 2000
# Shape of the chart's plot area (width / height). The degree-space render is
# stretched to it, so the image and the chart axes map the same way.
PLOT_RATIO = 1.3


def main() -> None:
    qgs = QgsApplication([], True)
    qgs.initQgis()
    lon0, lon1, lat0, lat1 = EXTENT
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    blds = rf.pg("raw", "os_buildings", "fid")
    blds.setRenderer(rf.QgsSingleSymbolRenderer(rf.fill("#E4E2DC")))
    roads = rf.pg("raw", "os_roads", "fid")
    roads.setRenderer(rf.QgsSingleSymbolRenderer(rf.QgsLineSymbol.createSimple(
        {"color": "#C9C7C0", "width": "0.25"})))
    boundary = rf.pg("raw", "boundaries", "code")
    boundary.setRenderer(rf.QgsSingleSymbolRenderer(rf.fill("0,0,0,0", "#8A7FC4", "0.6")))

    ms = rf.QgsMapSettings()
    ms.setLayers([boundary, roads, blds])
    ms.setDestinationCrs(wgs84)
    ms.setExtent(QgsRectangle(lon0, lat0, lon1, lat1))
    # Square pixels in degree space: the chart axes are linear in degrees too.
    ms.setOutputSize(rf.QSize(WIDTH, round(WIDTH * (lat1 - lat0) / (lon1 - lon0))))
    ms.setBackgroundColor(QColor("#FAFAF8"))
    ms.setOutputDpi(144)
    job = rf.QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image = job.renderedImage().scaled(
        WIDTH, round(WIDTH / PLOT_RATIO), rf.Qt.AspectRatioMode.IgnoreAspectRatio,
        rf.Qt.TransformationMode.SmoothTransformation)
    image.save(str(OUT))
    print("saved:", OUT)
    qgs.exitQgis()


if __name__ == "__main__":
    main()
