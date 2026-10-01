"""The four checks run once the satellite readings are loaded.

    beech-checks

1. Sanity test: the known drought years (2018, 2022) must read below each
   tree's normal. If they do not, the method is wrong.
2. Tree 10 (PK41290): when its crown disappeared, from its summer readings.
3. Field scores against the satellite: do trees scored as stressed read
   lower in 2026?
4. The case study tree against the council beeches, year by year.

Prints plain tables; the case study part prints readings only, never a
location.
"""

import pandas as pd

from beech.db import connect

BASELINE = (2019, 2020, 2021, 2023, 2024)
TREE_10 = "PK41290"


def query(sql: str, params=None) -> pd.DataFrame:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


def sanity() -> pd.DataFrame:
    """Median anomaly per year across analysable crowns, all species together."""
    return query("""
        SELECT y.year, count(*) AS crowns,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndvi)::numeric, 3) AS d_ndvi,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndmi)::numeric, 3) AS d_ndmi,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndre)::numeric, 3) AS d_ndre,
               round(avg((y.d_ndvi < 0)::int)::numeric, 2) AS share_below_normal
        FROM analysis.crown_anomaly y
        JOIN analysis.crown_analysable a USING (asset_id)
        GROUP BY y.year ORDER BY y.year""")


def tree_10() -> pd.DataFrame:
    """Every clear reading of tree 10, May to October, one row per image."""
    return query("""
        SELECT acquired_on, round(clear_frac::numeric, 2) AS clear,
               round(ndvi::numeric, 3) AS ndvi, round(ndmi::numeric, 3) AS ndmi
        FROM analysis.crown_obs_dated
        WHERE asset_id = %s AND clear_frac >= 0.9 AND ndvi IS NOT NULL
        ORDER BY acquired_on""", (TREE_10,))


def tree_10_by_year(obs: pd.DataFrame) -> pd.DataFrame:
    """Summer (July and August) median NDVI per year, and the neighbours'."""
    obs = obs.assign(year=pd.to_datetime(obs.acquired_on).dt.year,
                     month=pd.to_datetime(obs.acquired_on).dt.month)
    summer = obs[obs.month.isin([7, 8])].groupby("year").agg(
        n=("ndvi", "size"), ndvi=("ndvi", "median"))
    peers = query("""
        SELECT y.year, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY y.ndvi)::numeric, 3)
                   AS downs_beech_ndvi
        FROM analysis.crown_year y
        JOIN analysis.crowns c USING (asset_id)
        JOIN clean.trees t USING (asset_id)
        WHERE c.species_group = 'beech' AND t.site_name = 'Clifton and Durdham Downs'
          AND y.asset_id <> %s
        GROUP BY y.year""", (TREE_10,)).set_index("year")
    return summer.join(peers)


def field_vs_satellite() -> tuple[pd.DataFrame, pd.DataFrame, float | None]:
    rows = query("""
        SELECT tree_no, species_group, stressed, defoliation, discolour, dieback,
               mast, d_ndvi, d_ndmi, d_ndre, z_ndvi, why_no_comparison
        FROM analysis.field_vs_satellite ORDER BY tree_no""")
    both = rows[rows.why_no_comparison.isna() & rows.d_ndvi.notna()].copy()
    for c in ("d_ndvi", "d_ndmi", "d_ndre", "z_ndvi"):
        both[c] = both[c].astype(float)
    by_stress = both.groupby("stressed")[["d_ndvi", "d_ndmi", "d_ndre"]].agg(["count", "median"])
    rho = None
    if len(both) >= 5:
        # Spearman = Pearson on ranks (avoids a scipy dependency).
        rho = both["defoliation"].astype(float).rank().corr(both["d_ndvi"].rank())
    return rows, by_stress, rho


def case_study() -> pd.DataFrame:
    """The garden tree's summer readings and anomaly beside the council beeches'."""
    own = query("""
        SELECT c.year, count(*) AS n,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY o.ndvi) AS ndvi,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY o.ndmi) AS ndmi
        FROM private.case_study_obs o
        JOIN analysis.s2_candidates c USING (item_id)
        WHERE c.month IN (7, 8) AND o.clear_frac >= 0.9 AND o.ndvi IS NOT NULL
        GROUP BY c.year ORDER BY c.year""").set_index("year").astype(float)
    base = own.loc[own.index.isin(BASELINE)]
    own["d_ndvi"] = own.ndvi - base.ndvi.median()
    own["d_ndmi"] = own.ndmi - base.ndmi.median()
    peers = query("""
        SELECT y.year,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndvi) AS beech_d_ndvi,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndmi) AS beech_d_ndmi,
               count(*) AS beeches
        FROM analysis.crown_anomaly y
        JOIN analysis.crown_analysable a USING (asset_id)
        WHERE a.species_group = 'beech' AND a.size_class = '4: 80 cm and over'
        GROUP BY y.year""").set_index("year").astype(float)
    return own.join(peers).round(3)


def main() -> None:
    pd.set_option("display.width", 160)
    print("\n1. SANITY TEST: median change from each tree's normal, by year")
    print(sanity().to_string(index=False))
    print("\n2. TREE 10: summer NDVI by year, against Downs beeches")
    obs = tree_10()
    print(tree_10_by_year(obs).round(3).to_string())
    print("\n   every clear reading:")
    print(obs.to_string(index=False))
    print("\n3. FIELD SCORES AGAINST SATELLITE (2026)")
    rows, by_stress, rho = field_vs_satellite()
    print(rows.to_string(index=False))
    print(by_stress.round(3).to_string())
    print(f"   Spearman, defoliation class against NDVI change: {rho}")
    print("\n4. CASE STUDY TREE against large council beeches (80 cm and over)")
    print(case_study().to_string())


if __name__ == "__main__":
    main()
