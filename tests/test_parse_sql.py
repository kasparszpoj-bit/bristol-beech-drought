"""The SQL parsing functions, run against the real register strings."""

from decimal import Decimal

import pytest


def q(db, sql, *args):
    return db.execute(sql, args).fetchone()[0]


@pytest.mark.parametrize(
    "raw, unit, expected",
    [
        ("32 Centimetres", "cm", Decimal(32)),
        ("1 Centimetre", "cm", Decimal(1)),
        ("36 Centrimetres", "cm", Decimal(36)),  # typo in the register
        ("93  Centimetres", "cm", Decimal(93)),  # double space in the register
        ("15 Metres", "m", Decimal(15)),
        ("1 Metres", "m", Decimal(1)),
        ("2.5 Metres", "m", Decimal("2.5")),
        ("15 Metres", "cm", None),  # wrong unit for the field
        ("32 Centimetres", "m", None),
        ("No Code Allocated", "cm", None),
        ("Up to 20 M2 (New)", "m", None),
        ("", "m", None),
        (None, "m", None),
    ],
)
def test_parse_measure(db, raw, unit, expected):
    assert q(db, "SELECT clean.parse_measure(%s, %s)", raw, unit) == expected


@pytest.mark.parametrize(
    "raw, unit, expected",
    [
        ("32 Centimetres", "cm", "ok"),
        ("No Code Allocated", "cm", "missing"),
        (" no code allocated ", "cm", "missing"),
        (None, "cm", "missing"),
        ("", "cm", "missing"),
        ("15 Metres", "cm", "unparsed"),
        ("about 30", "cm", "unparsed"),
    ],
)
def test_measure_status(db, raw, unit, expected):
    assert q(db, "SELECT clean.measure_status(%s, %s)", raw, unit) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Planting Season 19/20", 2019),
        ("Planting Season 10/11", 2010),
        ("Planting Season 98/99", 1998),
        ("Not Applicable", None),
        (None, None),
    ],
)
def test_parse_planting_year(db, raw, expected):
    assert q(db, "SELECT clean.parse_planting_year(%s)", raw) == expected
