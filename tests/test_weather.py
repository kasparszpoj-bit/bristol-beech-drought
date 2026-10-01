from beech.ingest_weather import parse_line


def test_parses_a_plain_line():
    p = parse_line("   1977   9   18.3     8.1       0    48.6   117.9")
    assert (p["year"], p["month"], p["rain_mm"], p["sun_hours"]) == (
        1977, 9, 48.6, 117.9
    )
    assert not p["estimated"] and not p["provisional"]


def test_estimated_missing_and_provisional():
    p = parse_line(
        "   2026   7   26.5*   15.1       0     4.2    ---    Provisional"
    )
    assert p["tmax_c"] == 26.5 and p["estimated"]
    assert p["sun_hours"] is None
    assert p["provisional"]
    assert p["rain_mm"] == 4.2


def test_sunshine_sensor_hash_is_stripped():
    p = parse_line("   2026   7   27.7    13.9       0     2.2   342.2#  Provisional")
    assert p["sun_hours"] == 342.2 and not p["estimated"]


def test_missing_rain_is_none():
    p = parse_line("   1964   9   20.5     8.8       0     ---     ---")
    assert p["rain_mm"] is None


def test_header_lines_are_skipped():
    assert parse_line("   yyyy  mm   tmax    tmin      af    rain     sun") is None
    assert parse_line("Location: 355100E 123200N, Lat 51.006") is None
    assert parse_line("") is None
