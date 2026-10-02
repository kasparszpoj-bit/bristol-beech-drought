"""The comparisons behind the report, on the unmixed tree readings.

    beech-analysis

Writes outputs/tables/*.csv and prints them:
  years.csv            median change from normal by year, all species (the
                       sanity test: 2018 and 2022 must read below normal)
  species.csv          by species and year, with bootstrap 95% intervals,
                       for all analysable crowns and for crowns of similar
                       canopy share (0.70 to 0.85), so crown size cannot
                       drive the ranking
  beech_vs_others.csv  2026 difference, beech minus the other species
  beech_size.csv       beech by trunk size class (the age proxy)
  species_change.csv   2026 against 2018 by species, same trees, 95% intervals

Medians throughout, because a few badly mixed crowns can produce extreme
values. Bootstrap: 2,000 resamples, fixed seed, so reruns give the same
intervals.
"""

import numpy as np
import pandas as pd

from beech.checks import query
from beech.db import PROJECT_ROOT

TABLES = PROJECT_ROOT / "outputs" / "tables"
INDICES = ("d_ndvi", "d_ndmi", "d_ndre")
SPECIES = ("beech", "sycamore", "oak", "lime", "plane")
SHARE_BAND = (0.70, 0.85)
N_BOOT = 2000


def readings() -> pd.DataFrame:
    d = query("""
        SELECT a.asset_id, a.species_group AS species, a.size_class, a.site_type,
               a.canopy_share, y.year, y.n_obs, y.d_ndvi, y.d_ndmi, y.d_ndre
        FROM analysis.crown_anomaly_unmixed y
        JOIN analysis.crown_analysable_unmixed a USING (asset_id)""")
    for c in ("canopy_share", *INDICES):
        d[c] = pd.to_numeric(d[c])
    return d


def boot_median(x: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    b = np.median(rng.choice(x, (N_BOOT, len(x))), axis=1)
    return float(np.median(x)), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def by_year(d: pd.DataFrame) -> pd.DataFrame:
    out = d.groupby("year").agg(crowns=("asset_id", "size"),
                                **{c: (c, "median") for c in INDICES},
                                below_normal=("d_ndre", lambda s: (s < 0).mean()))
    return out.round(3).reset_index()


def by_species(d: pd.DataFrame, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for subset, part in (("all", d),
                         ("similar canopy share",
                          d[d.canopy_share.between(*SHARE_BAND)])):
        for (year, sp), g in part.groupby(["year", "species"]):
            row = {"subset": subset, "year": year, "species": sp, "crowns": len(g),
                   "canopy_share": round(g.canopy_share.median(), 2)}
            for c in INDICES:
                m, lo, hi = boot_median(g[c].to_numpy(), rng)
                row |= {c: m, f"{c}_lo": lo, f"{c}_hi": hi}
            rows.append(row)
    return pd.DataFrame(rows).round(3)


def beech_vs_others(d: pd.DataFrame, year: int = 2026, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    y = d[d.year == year]
    rows = []
    for c in INDICES:
        b = y[y.species == "beech"][c].dropna().to_numpy()
        o = y[y.species != "beech"][c].dropna().to_numpy()
        diffs = [np.median(rng.choice(b, len(b))) - np.median(rng.choice(o, len(o)))
                 for _ in range(N_BOOT)]
        rows.append({"year": year, "index": c, "beech": len(b), "others": len(o),
                     "difference": np.median(b) - np.median(o),
                     "lo": np.percentile(diffs, 2.5), "hi": np.percentile(diffs, 97.5)})
    return pd.DataFrame(rows).round(3)


def beech_by_size(d: pd.DataFrame, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for (year, size), g in d[d.species == "beech"].groupby(["year", "size_class"]):
        row = {"year": year, "size_class": size, "crowns": len(g)}
        for c in INDICES:
            m, lo, hi = boot_median(g[c].to_numpy(), rng)
            row |= {c: m, f"{c}_lo": lo, f"{c}_hi": hi}
        rows.append(row)
    return pd.DataFrame(rows).round(3)


def species_change(d: pd.DataFrame, before: int = 2018, after: int = 2026,
                   index: str = "d_ndre", seed: int = 2026) -> pd.DataFrame:
    """Each species' change between two droughts, on the same trees.

    Pairs every crown observed in both years, takes the median of its
    2026 minus 2018 change, and bootstraps a 95% interval. Negative means
    the species was more stressed in the later drought.
    """
    rng = np.random.default_rng(seed)
    w = (d[d.year.isin([before, after])]
         .pivot_table(index=["asset_id", "species"], columns="year", values=index)
         .dropna().reset_index())
    rows = []
    for sp, g in w.groupby("species"):
        diff = (g[after] - g[before]).to_numpy()
        boot = np.median(rng.choice(diff, (N_BOOT, len(diff))), axis=1)
        lo, hi = np.percentile(boot, 2.5), np.percentile(boot, 97.5)
        verdict = ("Worse in 2026" if hi < 0 else "Better in 2026" if lo > 0
                   else "No clear change")
        rows.append({"species": sp, "crowns": len(g),
                     f"change_{before}": g[before].median(),
                     f"change_{after}": g[after].median(),
                     "difference": np.median(diff), "difference_lo": lo,
                     "difference_hi": hi, "verdict": verdict})
    return pd.DataFrame(rows).round(3)


def main() -> None:
    pd.set_option("display.width", 200)
    TABLES.mkdir(parents=True, exist_ok=True)
    d = readings()
    tables = {
        "years": by_year(d),
        "species": by_species(d),
        "beech_vs_others": beech_vs_others(d),
        "beech_size": beech_by_size(d),
        "species_change": species_change(d),
    }
    for name, t in tables.items():
        t.to_csv(TABLES / f"{name}.csv", index=False)
    print(tables["years"].to_string(index=False))
    s = tables["species"]
    cols = ["subset", "species", "crowns", "canopy_share", "d_ndre", "d_ndre_lo", "d_ndre_hi",
            "d_ndmi", "d_ndvi"]
    for yr in (2018, 2022, 2026):
        print(f"\n{yr}")
        print(s[s.year == yr][cols].to_string(index=False))
    print("\n", tables["beech_vs_others"].to_string(index=False))
    b = tables["beech_size"]
    print("\n", b[b.year.isin([2018, 2026])][["year", "size_class", "crowns", "d_ndre",
                                            "d_ndre_lo", "d_ndre_hi", "d_ndmi"]].to_string(index=False))


if __name__ == "__main__":
    main()
