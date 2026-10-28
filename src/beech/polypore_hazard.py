"""Does a beech's drought stress predict giant polypore first appearing on it?

A discrete-time survival (hazard) model, fixed on 28 October 2026 before
the 2027 and 2028 seasons, so later years test it rather than tune it.
See docs/polypore_prediction.md.

- Unit: one analysable register beech in one year (2020 onwards).
- Event: the first year a precise record (30 m or better) falls within 15 m
  of the tree. A tree leaves the risk set after its event.
- 2019 is the first year of usable records, so a tree first seen then may
  have fruited for years before: those trees are left out (left truncation).
- Primary predictor: red edge stress in the previous year (minus the
  crown's NDRE anomaly against its own 2019 to 2024 baseline, so higher
  means more stressed). Red edge carried the 2026 stress in Phase 1.
  Same-year stress is reported only for comparison: a tree already rotting
  is stressed and fruiting in the same year, so it cannot show the order.
- Effort: log of all iNaturalist records in the 12 km circle that season.
- Model: binomial GLM with a complementary log-log link (the discrete-time
  form of a proportional hazards model). With about ten events only one
  stress term is fitted at a time. A permutation test (events reshuffled
  among trees at risk within each year) gives a p value that does not
  lean on large-sample theory.
"""

import math

import numpy as np
import pandas as pd
import statsmodels.api as sm

from beech.db import PROJECT_ROOT
from beech.figures import _read

FIRST_EVENT_YEAR = 2020
MATCH_M = 15
PERMUTATIONS = 2000
TERMS = {
    "stress_lag1": "previous year (primary)",
    "stress_lag13": "mean of 1 to 3 years before",
    "stress_same": "same year (comparison only)",
}
TABLES = PROJECT_ROOT / "outputs" / "tables"


def first_years() -> dict[str, int]:
    """First year each analysable beech had a precise record within 15 m."""
    df = _read(
        f"""
        SELECT t.asset_id, min(extract(year FROM r.observed_on))::int AS first_year
        FROM analysis.crown_analysable_unmixed t
        JOIN clean.trees c USING (asset_id)
        JOIN raw.polypore_records r
          ON r.accuracy_m <= 30 AND ST_DWithin(r.geom, c.geom, {MATCH_M})
        WHERE t.species_group = 'beech'
        GROUP BY t.asset_id
        """
    )
    return dict(zip(df["asset_id"], df["first_year"]))


def build_tree_years(stress: pd.DataFrame, effort: dict[int, int],
                     first: dict[str, int], last_year: int) -> pd.DataFrame:
    """Person-period table: one row per tree per year at risk.

    `stress` has columns asset_id, year, stress (higher = more stressed).
    """
    s = stress.set_index(["asset_id", "year"])["stress"]
    rows = []
    for tree in stress["asset_id"].unique():
        fy = first.get(tree)
        if fy is not None and fy < FIRST_EVENT_YEAR:
            continue  # left truncated: may have fruited long before 2019
        for year in range(FIRST_EVENT_YEAR, last_year + 1):
            lags = [s.get((tree, year - k)) for k in (1, 2, 3)]
            lags = [v for v in lags if v is not None and not math.isnan(v)]
            rows.append({
                "asset_id": tree,
                "year": year,
                "event": int(fy == year),
                "stress_same": s.get((tree, year)),
                "stress_lag1": s.get((tree, year - 1)),
                "stress_lag13": float(np.mean(lags)) if lags else None,
                "log_effort": math.log(effort[year]),
            })
            if fy == year:
                break
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame, term: str) -> dict:
    d = df.dropna(subset=[term])
    x = sm.add_constant(d[[term, "log_effort"]].astype(float))
    link = sm.families.links.CLogLog()
    res = sm.GLM(d["event"], x, family=sm.families.Binomial(link=link)).fit()
    beta = res.params[term]
    lo, hi = res.conf_int().loc[term]
    return {"term": term, "events": int(d["event"].sum()), "tree_years": len(d),
            "beta": beta, "ci_low": lo, "ci_high": hi, "p_wald": res.pvalues[term]}


def permutation_p(df: pd.DataFrame, term: str, observed: float,
                  n: int = PERMUTATIONS, seed: int = 1) -> float:
    """One sided: how often is a reshuffled beta at least as large?"""
    d = df.dropna(subset=[term]).copy()
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n):
        d["event"] = (
            d.groupby("year")["event"].transform(lambda e: rng.permutation(e.values))
        )
        try:
            beta = fit(d, term)["beta"]
        except (np.linalg.LinAlgError, ValueError):
            continue  # a reshuffle the model cannot fit; counts as no hit
        if beta >= observed:
            hits += 1
    return (hits + 1) / (n + 1)


def main() -> None:
    stress = _read(
        """
        SELECT a.asset_id, a.year, -a.d_ndre AS stress
        FROM analysis.crown_anomaly_unmixed a
        JOIN analysis.crown_analysable_unmixed t USING (asset_id)
        WHERE t.species_group = 'beech' AND a.n_obs >= 2
        """
    )
    eff = _read(
        "SELECT year, all_records FROM raw.inat_effort WHERE season_window = 'to_date'"
    )
    effort = dict(zip(eff["year"], eff["all_records"]))
    last_year = int(stress["year"].max())
    df = build_tree_years(stress, effort, first_years(), last_year)

    TABLES.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES / "polypore_tree_years.csv", index=False)
    results = []
    for term, label in TERMS.items():
        r = fit(df, term)
        r["label"] = label
        r["p_perm"] = permutation_p(df, term, r["beta"])
        # hazard ratio for a stress step of 0.05 (about a severe drought year)
        r["hr_per_0_05"] = math.exp(0.05 * r["beta"])
        results.append(r)
        print(
            f"{label}: {r['events']} events in {r['tree_years']} tree years, "
            f"hazard ratio per 0.05 stress {r['hr_per_0_05']:.2f} "
            f"(95% CI {math.exp(0.05 * r['ci_low']):.2f} to "
            f"{math.exp(0.05 * r['ci_high']):.2f}), permutation p {r['p_perm']:.2f}"
        )
    pd.DataFrame(results).to_csv(TABLES / "polypore_hazard.csv", index=False)


if __name__ == "__main__":
    main()
