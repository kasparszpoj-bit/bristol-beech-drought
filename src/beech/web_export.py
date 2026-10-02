"""Export the data behind the interactive web map.

    beech-web-export

Writes GeoJSON to web/data/: one point per analysable council tree (its
register position) with its yearly changes from normal, its crown outline
from the LIDAR, and the Bristol boundary. All in WGS84, coordinates rounded
to six decimal places (about 0.1 m).

Council trees only. Nothing is read from the private schema, so the case
study tree cannot appear on the map.
"""

import json

import pandas as pd

from beech.checks import query
from beech.db import PROJECT_ROOT

OUT = PROJECT_ROOT / "web" / "data"
YEARS = range(2018, 2027)

TREES_SQL = """
SELECT c.asset_id AS id, c.species_group AS species, t.common_name AS name,
       t.latin_name AS latin, t.site_name AS site, c.site_type,
       c.size_class AS size, round(c.dbh_cm)::int AS dbh,
       round(c.chm_max::numeric, 1)::float AS height,
       round(cc.canopy_share::numeric, 2)::float AS canopy,
       ST_AsGeoJSON(ST_Transform(t.geom, 4326), 6) AS geom
FROM analysis.crowns c
JOIN analysis.crown_analysable_unmixed a USING (asset_id)
JOIN clean.trees t USING (asset_id)
LEFT JOIN analysis.crown_cover cc USING (asset_id)
ORDER BY c.asset_id
"""

YEARS_SQL = """
SELECT y.asset_id AS id, y.year,
       round(y.d_ndre::numeric, 4)::float AS red_edge,
       round(y.d_ndvi::numeric, 4)::float AS greenness,
       round(y.d_ndmi::numeric, 4)::float AS moisture
FROM analysis.crown_anomaly_unmixed y
JOIN analysis.crown_analysable_unmixed a USING (asset_id)
"""

# Crowns simplified to 0.5 m in British National Grid before reprojecting.
CROWNS_SQL = """
SELECT c.asset_id AS id,
       ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(c.geom, 0.5), 4326), 6)
           AS geom
FROM analysis.crowns c
JOIN analysis.crown_analysable_unmixed a USING (asset_id)
ORDER BY c.asset_id
"""

BOUNDARY_SQL = """
SELECT ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(geom, 5), 4326), 5)
FROM raw.boundaries WHERE code = 'E06000023'
"""


def yearly(rows) -> dict[str, dict[str, list]]:
    """Per tree, one list per index with a value (or None) for every year."""
    out: dict[str, dict[str, list]] = {}
    for r in rows.itertuples(index=False):
        tree = out.setdefault(r.id, {k: [None] * len(YEARS)
                                     for k in ("red_edge", "greenness", "moisture")})
        i = int(r.year) - YEARS.start
        for k in tree:
            value = getattr(r, k)
            tree[k][i] = None if pd.isna(value) else value
    return out


def feature(geom: str, props: dict) -> dict:
    return {"type": "Feature", "geometry": json.loads(geom), "properties": props}


def write(name: str, features: list[dict]) -> None:
    path = OUT / f"{name}.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                               separators=(",", ":")), encoding="utf-8")
    print(f"{path.name}: {len(features):,} features, {path.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    trees = query(TREES_SQL)
    history = yearly(query(YEARS_SQL))
    points = []
    for t in trees.to_dict("records"):
        props = {k: (None if pd.isna(v) else v) for k, v in t.items() if k != "geom"}
        if props["dbh"] is not None:
            props["dbh"] = int(props["dbh"])
        props.update(history.get(t["id"], {}))
        points.append(feature(t["geom"], props))
    write("trees", points)

    write("crowns", [feature(r.geom, {"id": r.id})
                     for r in query(CROWNS_SQL).itertuples(index=False)])
    boundary = query(BOUNDARY_SQL).iloc[0, 0]
    write("boundary", [feature(boundary, {"name": "Bristol"})])


if __name__ == "__main__":
    main()
