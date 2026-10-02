"""Export clean tables for the Power BI report.

    python -m beech.powerbi_export

Writes CSVs to powerbi/data/, so the report opens anywhere without the
database. A star schema: one tree table (one row per mapped crown) and fact
tables keyed on asset_id or year. Coordinates are the council's register
points in WGS84, for Power BI maps.

Nothing from the private schema is exported except the case study tree's
yearly readings, which carry no location.
"""

import pandas as pd

from beech.checks import query
from beech.db import PROJECT_ROOT
from beech.figures import CASE_SQL, GRASS_SQL, PEERS_SQL, RAW_UNMIXED_SQL, TABLES

OUT = PROJECT_ROOT / "powerbi" / "data"

TREES_SQL = """
SELECT c.asset_id, c.species_group AS species, t.common_name, t.latin_name,
       t.purple_leaved, c.size_class, c.dbh_cm, c.crown_width_m,
       round(c.crown_area_m2::numeric, 1) AS crown_area_m2,
       round(c.chm_max::numeric, 1) AS height_m,
       t.site_name, c.site_type,
       round(cc.canopy_share::numeric, 3) AS canopy_share,
       (a.asset_id IS NOT NULL) AS analysable,
       f.tree_no AS field_tree_no,
       round(ST_Y(ST_Transform(t.geom, 4326))::numeric, 6) AS latitude,
       round(ST_X(ST_Transform(t.geom, 4326))::numeric, 6) AS longitude
FROM analysis.crowns c
JOIN clean.trees t USING (asset_id)
LEFT JOIN analysis.crown_cover cc USING (asset_id)
LEFT JOIN analysis.crown_analysable_unmixed a USING (asset_id)
LEFT JOIN analysis.field_sample f USING (asset_id)
ORDER BY c.asset_id
"""

TREE_YEAR_SQL = """
SELECT y.asset_id, y.year, y.n_obs AS clear_images,
       round(y.d_ndvi::numeric, 4) AS change_greenness,
       round(y.d_ndmi::numeric, 4) AS change_moisture,
       round(y.d_ndre::numeric, 4) AS change_red_edge,
       round(r.d_ndvi::numeric, 4) AS change_greenness_raw,
       -- Bands for colouring the map, on red edge change from normal.
       CASE WHEN y.d_ndre < -0.08 THEN '1 Strong drop'
            WHEN y.d_ndre < -0.03 THEN '2 Drop'
            WHEN y.d_ndre <= 0.03 THEN '3 Near normal'
            ELSE '4 Above normal' END AS change_band
FROM analysis.crown_anomaly_unmixed y
JOIN analysis.crown_analysable_unmixed a USING (asset_id)
LEFT JOIN analysis.crown_anomaly r ON r.asset_id = y.asset_id AND r.year = y.year
ORDER BY y.asset_id, y.year
"""

WEATHER_SQL = """
SELECT station, year, mar_aug_rain_mm AS growing_season_rain_mm,
       july_rain_mm, jja_mean_tmax_c AS summer_mean_max_c, provisional,
       dry_rank_mar_aug, dry_rank_july, hot_rank_summer, n_years,
       CASE WHEN year = 2026 THEN '2026'
            WHEN year IN (2018, 2022, 2025) THEN '2018, 2022, 2025'
            ELSE 'Other years' END AS year_group,
       station || ' ' || year AS station_year
FROM analysis.season_climate ORDER BY station, year
"""


def year_group(year: int) -> str:
    """The colour group for the drought years chart."""
    if year == 2026:
        return "2026"
    return "Known drought (2018, 2022)" if year in (2018, 2022) else "Other years"

FIELD_SQL = """
SELECT f.tree_no, f.asset_id, f.stratum, f.species_group AS species, f.size_class,
       f.visited, f.found, f.species_ok, f.defoliation AS thinning_class,
       f.discolour AS browning_class, f.dieback, f.leaf_fall, f.mast AS nut_crop,
       f.fungus, f.stressed, f.compared, f.excluded_reason,
       round(y.d_ndre::numeric, 4) AS change_red_edge_2026,
       round(y.d_ndmi::numeric, 4) AS change_moisture_2026,
       round(y.d_ndvi::numeric, 4) AS change_greenness_2026
FROM analysis.field_check f
LEFT JOIN analysis.crown_analysable_unmixed a USING (asset_id)
LEFT JOIN analysis.crown_anomaly_unmixed y
       ON y.asset_id = a.asset_id AND y.year = 2026
ORDER BY f.tree_no
"""


def whole_numbers(t: pd.DataFrame) -> pd.DataFrame:
    """Write whole-number columns as 12, not 12.0, even where some are blank.

    A column with blanks becomes a float in pandas and is written as "12.0",
    which Power BI reads as text and will not convert to a whole number.
    """
    t = t.copy()
    for c in t.columns:
        values = t[c].dropna()
        if t[c].dtype == bool or values.map(lambda v: isinstance(v, bool)).all():
            continue  # true/false columns stay true/false, blanks and all
        s = pd.to_numeric(t[c], errors="coerce") if t[c].dtype == object else t[c]
        if not pd.api.types.is_numeric_dtype(s):
            continue
        filled = s.dropna()
        if len(filled) and (filled == filled.round()).all() and s.notna().sum() == t[c].notna().sum():
            t[c] = s.astype("Int64")
    return t


def grass_vs_trees() -> pd.DataFrame:
    grass = query(GRASS_SQL)
    trees = query(RAW_UNMIXED_SQL)
    trees = trees[trees.species.isna() & trees.year.notna()].drop(columns="species")
    d = grass.merge(trees, on="year")
    d.columns = ["year", "grass", "trees_raw", "trees_ground_removed"]
    return d.astype(float).round(4).astype({"year": int})


def case_study() -> pd.DataFrame:
    own = query(CASE_SQL).astype(float)
    peers = query(PEERS_SQL).astype(float)
    d = own.merge(peers, on="year")
    d = d.rename(columns={"n": "clear_images", "d_ndvi": "case_greenness",
                          "d_ndre": "case_red_edge", "n_y": "large_beeches",
                          "ndre_med": "large_beech_red_edge_median",
                          "ndvi_med": "large_beech_greenness_median"})
    keep = ["year", "clear_images", "case_greenness", "case_red_edge",
            "large_beech_greenness_median", "large_beech_red_edge_median"]
    return d.rename(columns={"n_x": "clear_images"})[keep].round(4).astype({"year": int})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "trees": query(TREES_SQL),
        "tree_year": query(TREE_YEAR_SQL),
        "weather": query(WEATHER_SQL),
        "field_check": query(FIELD_SQL),
        "grass_vs_trees": grass_vs_trees(),
        "case_study": case_study(),
        "species_year": pd.read_csv(TABLES / "species.csv"),
        "species_change": pd.read_csv(TABLES / "species_change.csv"),
        "years": pd.read_csv(TABLES / "years.csv").assign(
            year_group=lambda d: d.year.map(year_group)),
    }
    for name, t in tables.items():
        t = whole_numbers(t)
        t.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name}.csv: {len(t):,} rows, {len(t.columns)} columns")


if __name__ == "__main__":
    main()
