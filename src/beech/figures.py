"""Report figures, built from the analysis views in PostGIS.

Style follows one fixed set of tokens so every figure reads as a set: a quiet
surface, hairline grid, grey for context, and at most two highlight colours
(both checked for colour-blind separation).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from beech.db import PROJECT_ROOT, connect

FIG_DIR = PROJECT_ROOT / "outputs" / "figures"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ACCENT = "#eb6834"  # the year the story is about
COMPARE = "#2a78d6"  # comparison years
BEFORE = "#6da7ec"  # a reading before the ground is removed (raw)
AFTER = "#184f95"  # the same reading after (unmixed)
TABLES = PROJECT_ROOT / "outputs" / "tables"
SPECIES = ["beech", "sycamore", "oak", "lime", "plane"]
SIZE_LABELS = {"2: 20 to 49 cm": "20 to 49 cm", "3: 50 to 79 cm": "50 to 79 cm",
               "4: 80 cm and over": "80 cm and over"}

# Hand-placed labels where two highlighted years sit close together.
LABEL_OFFSETS = {("Cardiff Bute Park", 2025): (0, -16, "center")}


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelcolor=INK_2, labelsize=9)


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _read(sql: str) -> pd.DataFrame:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def fig01_drought_context(out: Path | None = None) -> Path:
    """Each year's growing season rain against summer heat, per station."""
    df = _read("SELECT * FROM analysis.season_climate ORDER BY station, year")
    df["mar_aug_rain_mm"] = df["mar_aug_rain_mm"].astype(float)
    df["jja_mean_tmax_c"] = df["jja_mean_tmax_c"].astype(float)
    stations = ["Yeovilton", "Cardiff Bute Park"]
    compare_years = {2018, 2022, 2025}

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), sharey=True)
    fig.patch.set_facecolor(SURFACE)

    for ax, station in zip(axes, stations, strict=True):
        d = df[df.station == station]
        n = len(d)
        first = int(d.year.min())
        other = d[~d.year.isin(compare_years | {2026})]
        comp = d[d.year.isin(compare_years)]
        focus = d[d.year == 2026]

        _style(ax)
        ax.scatter(other.mar_aug_rain_mm, other.jja_mean_tmax_c, s=30,
                   color=MUTED, alpha=0.55, linewidths=0, label="Other years")
        ax.scatter(comp.mar_aug_rain_mm, comp.jja_mean_tmax_c, s=64, color=COMPARE,
                   edgecolors=SURFACE, linewidths=1.5, zorder=3,
                   label="2018, 2022, 2025")
        ax.scatter(focus.mar_aug_rain_mm, focus.jja_mean_tmax_c, s=110, color=ACCENT,
                   edgecolors=SURFACE, linewidths=1.5, zorder=4,
                   label="2026 (provisional)")

        for _, r in pd.concat([comp, focus]).iterrows():
            dx, dy, ha = LABEL_OFFSETS.get((station, int(r.year)), (7, 3, "left"))
            ax.annotate(str(int(r.year)), (r.mar_aug_rain_mm, r.jja_mean_tmax_c),
                        xytext=(dx, dy), textcoords="offset points", fontsize=9,
                        ha=ha, color=INK,
                        fontweight="bold" if r.year == 2026 else "normal")

        f = focus.iloc[0]
        ax.set_title(
            f"{station}, {first} to 2026 ({n} years)\n"
            f"2026: hottest summer, driest July, "
            f"{_ordinal(int(f.dry_rank_mar_aug))} driest growing season",
            fontsize=9.5, color=INK_2, loc="left",
        )
        ax.set_xlabel("Rainfall, March to August (mm)   ← drier",
                      fontsize=9, color=INK_2)

    axes[0].set_ylabel("Mean daily maximum, June to August (°C)   hotter →",
                       fontsize=9, color=INK_2)
    axes[1].legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="upper right")
    fig.suptitle("Summer 2026 was the hottest on record at both stations either "
                 "side of Bristol, after a dry spring and a dry 2025",
                 fontsize=11.5, color=INK, x=0.01, ha="left", y=0.99)
    fig.text(0.01, 0.005, "Source: Met Office historic station data. 2026 values "
             "are provisional. Each dot is one year.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96), w_pad=3)

    out = out or FIG_DIR / "fig01_drought_context.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out


def _save(fig, name: str) -> Path:
    out = FIG_DIR / name
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out


def _title(fig, title: str, note: str) -> None:
    fig.suptitle(title, fontsize=11.5, color=INK, x=0.01, ha="left", y=0.99)
    fig.text(0.01, 0.005, note, fontsize=8, color=MUTED)


def fig02_years() -> Path:
    """Median red edge change from normal, every year: the sanity test."""
    d = pd.read_csv(TABLES / "years.csv")
    colours = [ACCENT if y == 2026 else COMPARE if y in (2018, 2022) else MUTED
               for y in d.year]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    ax.bar(d.year, d.d_ndre, color=colours, width=0.62, edgecolor=SURFACE, linewidth=2)
    ax.axhline(0, color=AXIS, linewidth=1)
    for _, r in d.iterrows():
        below = r.d_ndre < 0
        ax.annotate(f"{r.below_normal:.0%}", (r.year, r.d_ndre),
                    xytext=(0, -12 if below else 4), textcoords="offset points",
                    ha="center", fontsize=8.5, color=INK_2)
    ax.set_xticks(d.year)
    ax.set_ylabel("Change in red edge from each tree's normal", fontsize=9, color=INK_2)
    ax.text(0.99, 0.97, "Percentages: share of crowns below their normal",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=INK_2)
    _title(fig, "Both known drought years read below normal; 2026 put the most "
                "crowns below normal of any year",
           f"July and August, {int(d.crowns.max()):,} council tree crowns, ground removed. "
           "Blue: known drought years. Orange: 2026.\nNormal = 2019 to 2021, 2023 and "
           "2024, so those years scatter around zero by design.")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    return _save(fig, "fig02_years.png")


GRASS_SQL = """
WITH yr AS (
    SELECT g.asset_id, s.year,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY g.ndvi) AS ndvi
    FROM analysis.grass_obs g JOIN analysis.s2_candidates s USING (item_id)
    WHERE s.month IN (7, 8) AND g.clear_frac >= 0.9 AND g.ndvi IS NOT NULL
    GROUP BY 1, 2
), base AS (
    SELECT asset_id, percentile_cont(0.5) WITHIN GROUP (ORDER BY ndvi) AS b
    FROM yr WHERE year IN (2019, 2020, 2021, 2023, 2024) GROUP BY 1
)
SELECT year, percentile_cont(0.5) WITHIN GROUP (ORDER BY ndvi - b) AS grass
FROM yr JOIN base USING (asset_id) GROUP BY year
"""

RAW_UNMIXED_SQL = """
SELECT a.species_group AS species, y.year,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY r.d_ndvi) AS raw,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndvi) AS unmixed
FROM analysis.crown_anomaly_unmixed y
JOIN analysis.crown_analysable_unmixed a USING (asset_id)
JOIN analysis.crown_anomaly r ON r.asset_id = y.asset_id AND r.year = y.year
GROUP BY ROLLUP (y.year, a.species_group)
"""


def fig03_ground() -> Path:
    """Why raw readings mislead: grass browns far more than trees."""
    grass = _read(GRASS_SQL).astype(float).set_index("year")
    ru = _read(RAW_UNMIXED_SQL)
    ru[["raw", "unmixed"]] = ru[["raw", "unmixed"]].astype(float)
    years = [2018, 2022, 2025, 2026]
    trees = ru[ru.species.isna() & ru.year.notna()].set_index("year")

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.8),
                               gridspec_kw={"width_ratios": [1.15, 1]})
    fig.patch.set_facecolor(SURFACE)
    _style(a)
    w = 0.26
    series = [("Open grass", [grass.grass[y] for y in years], MUTED),
              ("Tree crowns, raw", [trees.raw[y] for y in years], BEFORE),
              ("Tree crowns, ground removed", [trees.unmixed[y] for y in years], AFTER)]
    for i, (label, vals, colour) in enumerate(series):
        xs = [k + (i - 1) * w for k in range(len(years))]
        a.bar(xs, vals, width=w, color=colour, edgecolor=SURFACE, linewidth=2, label=label)
        for x, v in zip(xs, vals, strict=True):
            a.annotate(f"{v:+.2f}", (x, v), xytext=(0, -11 if v < 0 else 3),
                       textcoords="offset points", ha="center", fontsize=7.5, color=INK_2)
    a.axhline(0, color=AXIS, linewidth=1)
    a.set_xticks(range(len(years)), [str(y) for y in years])
    a.set_ylabel("Change in summer greenness (NDVI) from normal", fontsize=9, color=INK_2)
    a.set_ylim(top=0.14)
    a.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc="upper left")
    a.set_title("In dry summers grass browns far more than trees", fontsize=9.5,
                color=INK_2, loc="left")

    _style(b)
    sp = ru[(ru.year == 2026) & ru.species.notna()].set_index("species").loc[SPECIES[::-1]]
    ys = range(len(sp))
    for y, (name, r) in zip(ys, sp.iterrows(), strict=True):
        b.plot([r.raw, r.unmixed], [y, y], color=GRID, linewidth=3, zorder=1)
        b.annotate(name, (min(r.raw, r.unmixed), y), xytext=(-8, 0),
                   textcoords="offset points", ha="right", va="center", fontsize=9,
                   color=INK, fontweight="bold" if name == "beech" else "normal")
    b.scatter(sp.raw, ys, s=60, color=BEFORE, zorder=3, label="raw",
              edgecolors=SURFACE, linewidths=1.5)
    b.scatter(sp.unmixed, ys, s=60, color=AFTER, zorder=3, label="ground removed",
              edgecolors=SURFACE, linewidths=1.5)
    b.axvline(0, color=AXIS, linewidth=1)
    b.set_yticks([])
    lo = min(sp.raw.min(), sp.unmixed.min())
    b.set_xlim(lo - 0.03, 0.01)
    b.set_xlabel("Change in 2026 greenness (NDVI) from normal", fontsize=9, color=INK_2)
    b.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc="lower left")
    b.set_title("With the ground removed, beech stands apart", fontsize=9.5,
                color=INK_2, loc="left")
    _title(fig, "Most of the raw satellite signal was grass, not trees",
           "Open grass: 20 plots on the Downs. Crowns: the analysable council crowns. "
           "Ground removed using each crown's LIDAR canopy share and the ground around it.")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95), w_pad=3)
    return _save(fig, "fig03_ground.png")


def fig04_species() -> Path:
    """Species comparison, red edge, with bootstrap intervals, three drought years."""
    d = pd.read_csv(TABLES / "species.csv")
    d = d[d.subset == "all"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.9), sharex=True, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, yr in zip(axes, (2018, 2022, 2026), strict=True):
        _style(ax)
        t = d[d.year == yr].set_index("species").loc[SPECIES[::-1]]
        for y, (name, r) in enumerate(t.iterrows()):
            colour = ACCENT if name == "beech" else INK_2
            ax.plot([r.d_ndre_lo, r.d_ndre_hi], [y, y], color=colour, linewidth=2,
                    solid_capstyle="round", alpha=0.6)
            ax.scatter([r.d_ndre], [y], s=58, color=colour, zorder=3,
                       edgecolors=SURFACE, linewidths=1.5)
        ax.axvline(0, color=AXIS, linewidth=1)
        labels = [f"{n} ({int(c)})" for n, c in zip(t.index, t.crowns, strict=True)]
        ax.set_yticks(range(len(t)), labels)
        ax.set_title(str(yr), fontsize=10, color=INK, loc="left",
                     fontweight="bold" if yr == 2026 else "normal")
    axes[1].set_xlabel("Change in red edge from each tree's normal (median, 95% interval)",
                       fontsize=9, color=INK_2)
    _title(fig, "In 2026 beech was among the hardest hit, with oak and sycamore; "
                "lime and plane much less",
           "July and August, ground removed. Bars: bootstrap 95% intervals of the median. "
           "Numbers in brackets: crowns. In 2018 oak was hit hardest.")
    fig.tight_layout(rect=(0, 0.03, 1, 0.94), w_pad=2)
    return _save(fig, "fig04_species.png")


def fig05_beech_size() -> Path:
    """Beech by trunk size class (the age proxy), 2018 and 2026."""
    d = pd.read_csv(TABLES / "beech_size.csv")
    d = d[d.size_class.isin(SIZE_LABELS) & d.year.isin([2018, 2026])]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    order = list(SIZE_LABELS)
    for yr, colour, dy in ((2018, COMPARE, 0.14), (2026, ACCENT, -0.14)):
        t = d[d.year == yr].set_index("size_class").loc[order]
        ys = [i + dy for i in range(len(order))]
        ax.hlines(ys, t.d_ndre_lo, t.d_ndre_hi, color=colour, linewidth=2, alpha=0.6)
        ax.scatter(t.d_ndre, ys, s=58, color=colour, zorder=3, edgecolors=SURFACE,
                   linewidths=1.5, label=str(yr))
    counts = d[d.year == 2026].set_index("size_class").loc[order].crowns
    ax.set_yticks(range(len(order)),
                  [f"{SIZE_LABELS[k]} ({int(counts[k])})" for k in order])
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.set_xlabel("Change in red edge from each tree's normal (median, 95% interval)",
                  fontsize=9, color=INK_2)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="upper left")
    _title(fig, "The oldest beeches were not clearly worse",
           "Council beeches by trunk diameter (the age proxy); numbers in brackets: crowns. "
           "Intervals overlap in both years.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return _save(fig, "fig05_beech_size.png")


CASE_SQL = """
WITH u AS (
    SELECT s.year, s.month,
           (o.ndvi - (1 - c.canopy_share) * g.ndvi) / c.canopy_share AS ndvi,
           (o.ndre - (1 - c.canopy_share) * g.ndre) / c.canopy_share AS ndre
    FROM private.case_study_obs o
    JOIN private.case_study_ground g USING (item_id)
    JOIN analysis.s2_candidates s USING (item_id), private.case_study_crown c
    WHERE o.clear_frac >= 0.9 AND o.ndvi IS NOT NULL
      AND g.ndvi IS NOT NULL AND g.ndvi_px >= 2
), yr AS (
    SELECT year, count(*) AS n,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY ndvi) AS ndvi,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY ndre) AS ndre
    FROM u WHERE month IN (7, 8) GROUP BY year
), b AS (
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY ndvi) AS bv,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY ndre) AS br
    FROM yr WHERE year IN (2019, 2020, 2021, 2023, 2024)
)
SELECT year, n, ndvi - bv AS d_ndvi, ndre - br AS d_ndre FROM yr, b ORDER BY year
"""

PEERS_SQL = """
SELECT y.year,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY y.d_ndre) AS ndre_q1,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndre) AS ndre_med,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY y.d_ndre) AS ndre_q3,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY y.d_ndvi) AS ndvi_q1,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY y.d_ndvi) AS ndvi_med,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY y.d_ndvi) AS ndvi_q3,
       count(*) AS n
FROM analysis.crown_anomaly_unmixed y
JOIN analysis.crown_analysable_unmixed a USING (asset_id)
WHERE a.species_group = 'beech' AND a.size_class = '4: 80 cm and over'
GROUP BY y.year ORDER BY y.year
"""


def fig06_case_study() -> Path:
    """The garden tree against the large council beeches, year by year. No map."""
    own = _read(CASE_SQL).astype(float)
    peers = _read(PEERS_SQL).astype(float)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, idx, label in ((axes[0], "ndre", "red edge"),
                           (axes[1], "ndvi", "greenness (NDVI)")):
        _style(ax)
        ax.fill_between(peers.year, peers[f"{idx}_q1"], peers[f"{idx}_q3"], color=GRID,
                        label=f"large council beeches, middle half ({int(peers.n.max())})")
        ax.plot(peers.year, peers[f"{idx}_med"], color=MUTED, linewidth=2,
                label="large council beeches, median")
        ax.plot(own.year, own[f"d_{idx}"], color=ACCENT, linewidth=2,
                label="case study tree")
        solid, thin = own[own.n >= 4], own[own.n < 4]
        ax.scatter(solid.year, solid[f"d_{idx}"], s=46, color=ACCENT, zorder=3,
                   edgecolors=SURFACE, linewidths=1.5)
        ax.scatter(thin.year, thin[f"d_{idx}"], s=46, color=SURFACE, zorder=3,
                   edgecolors=ACCENT, linewidths=1.5)
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.set_title(f"Change in {label} from normal", fontsize=9.5, color=INK_2, loc="left")
        ax.set_xticks(range(2018, 2027))
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK_2, loc="upper right")
    _title(fig, "The case study tree lost more greenness and red edge in 2026 than "
                "most large council beeches",
           "July and August, ground removed. Large: trunk 80 cm and over. Hollow points: "
           "fewer than four clear images that summer. About half of the garden tree's "
           "reading is ground, so its line is noisier.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94), w_pad=3)
    return _save(fig, "fig06_case_study.png")


def main() -> None:
    for fn in (fig01_drought_context, fig02_years, fig03_ground, fig04_species,
               fig05_beech_size, fig06_case_study):
        print(fn())


if __name__ == "__main__":
    main()
