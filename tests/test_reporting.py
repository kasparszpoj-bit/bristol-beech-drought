"""The statistics and the exports behind the report, web map and Power BI."""

import numpy as np
import pandas as pd

from beech import analysis, web_export
from beech.powerbi_export import whole_numbers


def test_whole_numbers_drops_the_decimal_point_with_blanks():
    t = whole_numbers(pd.DataFrame({"id": ["a", "b", "c"], "tree_no": [1.0, None, 12.0]}))
    assert t.tree_no.dtype == "Int64"
    assert t.to_csv(index=False, lineterminator="\n") == "id,tree_no\na,1\nb,\nc,12\n"


def test_whole_numbers_leaves_decimals_text_and_ids_alone():
    t = whole_numbers(pd.DataFrame({
        "change": [-0.0123, 0.5],
        "asset_id": ["00809493", "PK41290"],
        "species": ["beech", "oak"],
    }))
    assert t.change.tolist() == [-0.0123, 0.5]
    # IDs that look like numbers must keep their leading zeros.
    assert t.asset_id.tolist() == ["00809493", "PK41290"]


def test_whole_numbers_keeps_true_false_columns():
    t = whole_numbers(pd.DataFrame({"id": ["a", "b", "c"], "stressed": [True, None, False]}, dtype=object))
    assert t.to_csv(index=False, lineterminator="\n") == "id,stressed\na,True\nb,\nc,False\n"


def test_boot_median_interval_contains_the_median():
    rng = np.random.default_rng(1)
    x = rng.normal(-0.05, 0.02, 200)
    m, lo, hi = analysis.boot_median(x, np.random.default_rng(2026))
    assert lo < m < hi
    assert abs(m - np.median(x)) < 1e-12
    assert hi - lo < 0.02  # 200 values: a tight interval


def test_boot_median_ignores_missing_and_handles_empty():
    m, _, _ = analysis.boot_median(np.array([1.0, np.nan, 3.0]), np.random.default_rng(0))
    assert m == 2.0
    assert all(np.isnan(analysis.boot_median(np.array([np.nan]), np.random.default_rng(0))))


def readings(diff_beech: float, diff_oak: float, n: int = 60) -> pd.DataFrame:
    """Paired 2018 and 2026 readings with a known change for each species."""
    rng = np.random.default_rng(7)
    rows = []
    for sp, diff in (("beech", diff_beech), ("oak", diff_oak)):
        for i in range(n):
            base = rng.normal(-0.04, 0.02)
            rows.append({"asset_id": f"{sp}{i}", "species": sp, "year": 2018, "d_ndre": base})
            rows.append({"asset_id": f"{sp}{i}", "species": sp, "year": 2026,
                         "d_ndre": base + diff + rng.normal(0, 0.003)})
    # A crown seen in 2026 only must not be paired.
    rows.append({"asset_id": "lonely", "species": "beech", "year": 2026, "d_ndre": -0.5})
    return pd.DataFrame(rows)


def test_species_change_pairs_trees_and_gives_verdicts():
    out = analysis.species_change(readings(-0.02, 0.0)).set_index("species")
    assert out.loc["beech", "crowns"] == 60  # the unpaired crown is dropped
    assert out.loc["beech", "difference"] == -0.02
    assert out.loc["beech", "verdict"] == "Worse in 2026"
    assert out.loc["oak", "verdict"] == "No clear change"


def test_species_change_better():
    out = analysis.species_change(readings(0.0, 0.015)).set_index("species")
    assert out.loc["oak", "verdict"] == "Better in 2026"
    assert out.loc["oak", "difference_lo"] > 0


def test_web_export_yearly_fills_every_year():
    rows = pd.DataFrame({"id": ["A", "A"], "year": [2018, 2026],
                         "red_edge": [-0.04, np.nan], "greenness": [0.0, -0.01],
                         "moisture": [0.01, 0.02]})
    tree = web_export.yearly(rows)["A"]
    assert len(tree["red_edge"]) == 9
    assert tree["red_edge"][0] == -0.04
    assert tree["red_edge"][8] is None  # NaN becomes null in the GeoJSON
    assert tree["greenness"][8] == -0.01
    assert tree["moisture"][1] is None  # a year with no reading
