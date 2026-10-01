import json

import pytest

from beech.ingest_register import feature_to_row, where_clause


def test_where_clause_covers_all_genera():
    w = where_clause(("Fagus", "Tilia"))
    assert w == "LATIN_NAME LIKE 'Fagus%' OR LATIN_NAME LIKE 'Tilia%'"


def test_empty_genera_means_whole_register():
    assert where_clause(()) == "1=1"


def test_feature_to_row_uses_geometry():
    f = {
        "attributes": {"OBJECTID": 7, "DBH": "No Code Allocated", "X": 1, "Y": 2},
        "geometry": {"x": 358148.2, "y": 174100.9},
    }
    oid, attrs, x, y = feature_to_row(f)
    assert (oid, x, y) == (7, 358148.2, 174100.9)
    assert json.loads(attrs)["DBH"] == "No Code Allocated"  # kept untouched


def test_feature_to_row_falls_back_to_xy_fields():
    f = {"attributes": {"OBJECTID": 8, "X": 360148.1, "Y": 168420.6}}
    assert feature_to_row(f)[2:] == (360148.1, 168420.6)


def test_feature_to_row_rejects_missing_coordinates():
    with pytest.raises(ValueError):
        feature_to_row({"attributes": {"OBJECTID": 9}})
