import datetime as dt

from beech.ingest_polypore import effort_windows, inat_row, nbn_row


def test_inat_row_keeps_location_and_drops_people():
    obs = {
        "id": 409405283,
        "observed_on": "2026-10-19",
        "geojson": {"type": "Point", "coordinates": [-2.588, 51.473]},
        "positional_accuracy": 15,
        "quality_grade": "needs_id",
        "license_code": "cc-by-nc",
        "user": {"id": 1, "login": "someone"},
    }
    row = inat_row(obs)
    assert (row["lat"], row["lon"], row["accuracy_m"]) == (51.473, -2.588, 15)
    assert row["url"].endswith("/409405283")
    assert "someone" not in str(row)


def test_inat_row_without_location_is_dropped():
    assert inat_row({"id": 1, "geojson": None}) is None


def test_nbn_row_handles_pre_1970_dates():
    occ = {
        "uuid": "abc",
        "eventDate": -457488000000,  # 1955-07-04
        "decimalLatitude": 51.44,
        "decimalLongitude": -2.65,
        "coordinateUncertaintyInMeters": 707.1,
        "dataResourceName": "Fungal Records Database of Britain and Ireland",
        "license": "CC-BY",
    }
    row = nbn_row(occ)
    assert row["observed_on"] == "1955-07-04"
    assert row["accuracy_m"] == 707.1


def test_effort_windows_compare_like_for_like():
    w = effort_windows(dt.date(2026, 10, 28))
    to_date = [x for x in w if x[1] == "to_date"]
    assert all((x[3].month, x[3].day) == (10, 28) for x in to_date)
    assert not any(x[0] == 2026 and x[1] == "full" for x in w)
    assert (2025, "full", dt.date(2025, 8, 1), dt.date(2025, 12, 31)) in w


def test_tree_years_risk_set_and_left_truncation():
    import pandas as pd

    from beech.polypore_hazard import build_tree_years

    stress = pd.DataFrame({
        "asset_id": ["A"] * 4 + ["B"] * 4 + ["C"] * 4,
        "year": [2019, 2020, 2021, 2022] * 3,
        "stress": [0.01, 0.02, 0.05, 0.03] * 3,
    })
    effort = {2020: 1000, 2021: 1000, 2022: 1000}
    first = {"A": 2021, "C": 2019}  # B never recorded, C seen in 2019
    df = build_tree_years(stress, effort, first, 2022)
    a = df[df.asset_id == "A"]
    assert list(a.year) == [2020, 2021]  # leaves the risk set after its event
    assert list(a.event) == [0, 1]
    assert a.iloc[1]["stress_lag1"] == 0.02
    assert list(df[df.asset_id == "B"].year) == [2020, 2021, 2022]
    assert "C" not in set(df.asset_id)  # left truncated
