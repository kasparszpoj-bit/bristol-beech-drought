"""Render the QGIS-made report figures, with QGIS's own Python.

    "C:\\Program Files\\QGIS 4.0.3\\bin\\python-qgis.bat" qgis/scripts/render_figures.py [name ...]

Run without QT_QPA_PLATFORM=offscreen, or text renders as boxes. Name
figures to render only those: model01, model02, crown_method, study_area.

Writes to outputs/figures/:
  model01_tree_crowns.png   the model 01 diagram, as drawn by the Graphical Modeler
  model02_crown_indices.png the model 02 diagram
  fig_crown_method.png      how a crown is drawn: canopy, zones, crowns
  fig_study_area.png        Bristol, the study area and every council beech
Layers are read live from the PostGIS database.
"""

import sys
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsColorRampShader,
    QgsCoordinateReferenceSystem,
    QgsDataSourceUri,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsMarkerSymbol,
    QgsProcessingContext,
    QgsProcessingModelAlgorithm,
    QgsProperty,
    QgsRasterLayer,
    QgsRasterShader,
    QgsRectangle,
    QgsRendererCategory,
    QgsSingleBandPseudoColorRenderer,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QRectF, QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "outputs" / "figures"
CHM = ROOT / "data" / "lidar" / "chm.tif"
MODELS = ROOT / "qgis" / "models"
BNG = QgsCoordinateReferenceSystem("EPSG:27700")

INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
ACCENT, COMPARE = "#eb6834", "#2a78d6"


def pg(schema, table, key, where=""):
    u = QgsDataSourceUri()
    u.setConnection("localhost", "5432", "beech", "postgres", "")
    u.setDataSource(schema, table, "geom", where, key)
    u.setSrid("27700")
    layer = QgsVectorLayer(u.uri(False), table, "postgres")
    if not layer.isValid():
        raise RuntimeError(f"invalid layer {schema}.{table}")
    return layer


def fill(color, outline="0,0,0,0", width="0.2"):
    return QgsFillSymbol.createSimple(
        {"color": color, "outline_color": outline, "outline_width": width})


def dot(color, size, outline="#ffffff"):
    return QgsMarkerSymbol.createSimple(
        {"name": "circle", "color": color, "size": str(size),
         "outline_color": outline, "outline_width": "0.25"})


def chm_layer():
    layer = QgsRasterLayer(str(CHM), "chm")
    sh = QgsColorRampShader(0, 30)
    sh.setColorRampType(QgsColorRampShader.Type.Interpolated)
    sh.setColorRampItemList([
        QgsColorRampShader.ColorRampItem(0, QColor("#f4f4f0")),
        QgsColorRampShader.ColorRampItem(4.99, QColor("#ecece6")),
        QgsColorRampShader.ColorRampItem(5, QColor("#cfe3c1")),
        QgsColorRampShader.ColorRampItem(15, QColor("#6fa55e")),
        QgsColorRampShader.ColorRampItem(30, QColor("#1f4d1c")),
    ])
    rs = QgsRasterShader()
    rs.setRasterShaderFunction(sh)
    layer.setRenderer(QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, rs))
    return layer


def render(layers, extent, size):
    ms = QgsMapSettings()
    ms.setLayers(layers)
    ms.setDestinationCrs(BNG)
    ms.setExtent(extent)
    ms.setOutputSize(QSize(*size))
    ms.setBackgroundColor(QColor("#fcfcfb"))
    ms.setOutputDpi(144)
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    return job.renderedImage()


def text(painter, x, y, w, h, s, size=13, color=INK, bold=False,
         align=Qt.AlignmentFlag.AlignLeft):
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    painter.setFont(f)
    painter.setPen(QColor(color))
    painter.drawText(QRectF(x, y, w, h), int(align | Qt.AlignmentFlag.AlignVCenter), s)


def model_diagram(model: str, name: str):
    from qgis.gui import QgsModelGraphicsScene

    m = QgsProcessingModelAlgorithm()
    m.fromFile(str(MODELS / model))
    scene = QgsModelGraphicsScene()
    scene.setModel(m)
    scene.createItems(m, QgsProcessingContext())
    rect = scene.itemsBoundingRect().adjusted(-30, -30, 30, 30)
    img = QImage(int(rect.width() * 2), int(rect.height() * 2), QImage.Format.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(p, QRectF(0, 0, img.width(), img.height()), rect)
    p.end()
    out = FIG / name
    img.save(str(out))
    return out


def crown_method():
    import processing

    ext = QgsRectangle(357150, 175250, 357450, 175550)  # 300 m on Durdham Down
    area = (f"ST_Intersects(geom, ST_MakeEnvelope({ext.xMinimum() - 60}, {ext.yMinimum() - 60}, "
            f"{ext.xMaximum() + 60}, {ext.yMaximum() + 60}, 27700))")
    chm = chm_layer()
    blds = pg("raw", "os_buildings", "fid", area)
    blds.setRenderer(QgsSingleSymbolRenderer(fill("150,150,150,160", "#6b6b6b", "0.25")))
    trees = pg("clean", "trees", "objectid", f"in_study_area AND {area}")
    trees.setRenderer(QgsSingleSymbolRenderer(dot("#0b0b0b", 1.2)))
    crowns = pg("analysis", "crowns", "fid", area)
    colours = {"beech": ACCENT, "oak": COMPARE, "lime": "#9ec5f4", "plane": "#b8b7ae",
               "sycamore": "#dcdbd3"}
    crowns.setRenderer(QgsCategorizedSymbolRenderer("species_group", [
        QgsRendererCategory(k, fill(v, "#0b0b0b", "0.25"), k) for k, v in colours.items()]))

    T = "TEMPORARY_OUTPUT"
    targets = processing.run("native:extractbyexpression", {
        "INPUT": trees, "OUTPUT": T,
        "EXPRESSION": '"in_comparison" AND ("dbh_cm" >= 40 OR "crown_width_m" >= 10)'})["OUTPUT"]
    circles = processing.run("native:buffer", {
        "INPUT": targets, "SEGMENTS": 16, "DISSOLVE": False, "OUTPUT": T,
        "DISTANCE": QgsProperty.fromExpression(
            'min(max(coalesce("crown_width_m" / 2, 8), 4), 12) + 2')})["OUTPUT"]
    cells = processing.run("native:voronoipolygons", {
        "INPUT": trees, "BUFFER": 5, "OUTPUT": T})["OUTPUT"]
    circles.setRenderer(QgsSingleSymbolRenderer(fill("0,0,0,0", ACCENT, "0.5")))
    cells.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple(
        {"color": COMPARE, "width": "0.3"}).clone() if False else
        fill("0,0,0,0", COMPARE, "0.3")))

    panels = [
        ("1  Canopy height from LIDAR", "Roofs (grey) look like canopy",
         [trees, blds, chm]),
        ("2  Zones", "Search circle (orange) x Voronoi cell (blue)",
         [trees, circles, cells, chm]),
        ("3  Crowns", "Beech orange, oak blue, others grey",
         [trees, crowns, blds, chm]),
    ]
    # Text sized to stay readable when the figure is shown small (README, Power BI).
    size, pad, head = 820, 24, 160
    img = QImage(3 * size + 4 * pad, size + head + 80, QImage.Format.Format_ARGB32)
    img.fill(QColor("#fcfcfb"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, (title, sub, layers) in enumerate(panels):
        x = pad + i * (size + pad)
        text(p, x, 12, size, 70, title, 40, INK, True)
        text(p, x, 88, size, 60, sub, 30, INK_2)
        p.drawImage(x, head, render(layers, ext, (size, size)))
    text(p, pad, head + size + 12, 3 * size, 60,
         "Durdham Down, 300 m square. LIDAR: Environment Agency composite, 1 m. "
         "Buildings: OS OpenMap Local. Trees: Bristol City Council register.",
         24, MUTED)
    p.end()
    out = FIG / "fig_crown_method.png"
    img.save(str(out))
    return out


def study_area():
    boundary = pg("raw", "boundaries", "code")
    boundary.setRenderer(QgsSingleSymbolRenderer(fill("0,0,0,0", "#4a3aa7", "0.7")))
    u = QgsDataSourceUri()
    u.setConnection("localhost", "5432", "beech", "postgres", "")
    u.setDataSource("", "(SELECT 1 AS id, geom FROM analysis.study_area)", "geom", "", "id")
    u.setSrid("27700")
    study = QgsVectorLayer(u.uri(False), "study", "postgres")
    study.setRenderer(QgsSingleSymbolRenderer(fill("0,0,0,0", INK, "0.5")))
    blds = pg("raw", "os_buildings", "fid")
    blds.setRenderer(QgsSingleSymbolRenderer(fill("#e1e0d9")))
    beech = pg("clean", "trees", "objectid", "species_group = 'beech'")
    ramp = {"4: 80 cm and over": ("#184f95", 3.0), "3: 50 to 79 cm": ("#2a78d6", 2.4),
            "2: 20 to 49 cm": ("#6da7ec", 1.8), "1: under 20 cm": ("#9ec5f4", 1.4),
            "unknown": ("#c3c2b7", 1.4)}
    beech.setRenderer(QgsCategorizedSymbolRenderer("size_class", [
        QgsRendererCategory(k, dot(c, s), k) for k, (c, s) in ramp.items()]))
    ext = study.extent()
    ext.grow(300)
    w = 1400
    h = int(w * ext.height() / ext.width())
    img = QImage(w, h + 150, QImage.Format.Format_ARGB32)
    img.fill(QColor("#fcfcfb"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    text(p, 20, 8, w, 40, "Bristol's 985 council beeches, by trunk size", 18, INK, True)
    text(p, 20, 46, w, 30, "Purple line: Bristol boundary (ONS). Black box: study area "
         "(boundary plus 3 km, around every comparison tree).", 12, INK_2)
    p.drawImage(0, 80, render([beech, study, boundary, blds], ext, (w, h)))
    lx, ly = 30, h + 92
    for k, (c, s) in ramp.items():
        p.setBrush(QColor(c))
        p.setPen(QColor("#ffffff"))
        r = 5 + s * 2
        p.drawEllipse(QRectF(lx, ly + 12 - r / 2, r, r))
        text(p, lx + 22, ly, 220, 24, k.split(": ")[-1], 12, INK_2)
        lx += 240
    text(p, 20, h + 118, w, 30, "Trunk size is the age proxy. Source: Bristol City Council "
         "tree register (OGL); OS OpenMap Local buildings.", 11, MUTED)
    p.end()
    out = FIG / "fig_study_area.png"
    img.save(str(out))
    return out


def main() -> None:
    qgs = QgsApplication([], True)
    qgs.initQgis()
    sys.path.append(str(Path(QgsApplication.pkgDataPath()) / "python" / "plugins"))
    from processing.core.Processing import Processing

    Processing.initialize()
    FIG.mkdir(parents=True, exist_ok=True)
    figures = {
        "model01": lambda: model_diagram("01_tree_crowns.model3", "model01_tree_crowns.png"),
        "model02": lambda: model_diagram("02_crown_indices.model3", "model02_crown_indices.png"),
        "crown_method": crown_method,
        "study_area": study_area,
    }
    for name in sys.argv[1:] or figures:
        print("saved:", figures[name]())
    qgs.exitQgis()


if __name__ == "__main__":
    main()
