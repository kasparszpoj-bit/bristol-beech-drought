"""Make the public copy of the QGIS project, without the private case study.

    "C:\\Program Files\\QGIS 4.0.3\\bin\\python-qgis.bat" qgis/scripts/make_public_project.py

The working project (with the garden tree, read from the private schema) is
kept outside the repo, in ../_private/beech_case_study/. This writes
qgis/beech_drought.qgz with every layer that reads the private schema
removed and the default view set to the study area, so the published
project holds no trace of the tree's location.
"""

import shutil
import sys
from pathlib import Path

from qgis.core import QgsApplication, QgsProject, QgsRectangle, QgsReferencedRectangle

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "qgis" / "beech_drought.qgz"
PRIVATE = ROOT.parent / "_private" / "beech_case_study" / "beech_drought_private.qgz"
STUDY_AREA = QgsRectangle(350000, 166000, 366000, 182000)  # British National Grid


def main() -> None:
    qgs = QgsApplication([], False)
    qgs.initQgis()
    if not PRIVATE.exists():
        PRIVATE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PUBLIC, PRIVATE)
        print("working project kept at", PRIVATE)
    project = QgsProject.instance()
    if not project.read(str(PRIVATE)):
        sys.exit(f"could not read {PRIVATE}")
    # The working copy lives one folder over, so relative raster paths can
    # resolve into _private/; point them back at this project's data/.
    for layer in project.mapLayers().values():
        src = layer.source().replace("\\", "/")
        if "/_private/data/" in src:
            fixed = src.replace("/_private/data/", "/bristol_beech_drought_2026/data/")
            layer.setDataSource(fixed, layer.name(), layer.providerType())
    project.write(str(PRIVATE))
    removed = []
    for layer in list(project.mapLayers().values()):
        source = layer.source()
        if 'table="private"' in source or "case_study" in source.lower():
            removed.append(layer.name())
            project.removeMapLayer(layer.id())
    for bookmark in project.bookmarkManager().bookmarks():
        project.bookmarkManager().removeBookmark(bookmark.id())
    project.viewSettings().setDefaultViewExtent(
        QgsReferencedRectangle(STUDY_AREA, project.crs()))
    if not project.write(str(PUBLIC)):
        sys.exit(f"could not write {PUBLIC}")
    print("removed:", removed or "nothing")
    print("public project:", PUBLIC)
    qgs.exitQgis()


if __name__ == "__main__":
    main()
