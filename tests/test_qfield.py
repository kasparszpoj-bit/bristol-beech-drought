import sqlite3
import struct

import pytest

from beech import qfield

POINT = struct.pack("<BIdd", 1, 1, 357000.0, 175000.0)  # WKB point, little endian


def gp(flags: int, envelope: bytes = b"") -> bytes:
    return b"GP" + bytes([0, flags]) + struct.pack("<i", 27700) + envelope + POINT


def test_gpkg_wkb_no_envelope():
    assert qfield.gpkg_wkb(gp(0b00000001)) == POINT


def test_gpkg_wkb_xy_envelope():
    env = struct.pack("<4d", 357000, 357000, 175000, 175000)
    assert qfield.gpkg_wkb(gp(0b00000011, env)) == POINT


def test_gpkg_wkb_rejects_other_blobs():
    with pytest.raises(ValueError):
        qfield.gpkg_wkb(POINT)


@pytest.fixture
def returned(tmp_path, monkeypatch):
    """A returned project: two trees visited, one not, photos flattened."""
    monkeypatch.setattr(qfield, "PROJECT_ROOT", tmp_path)
    folder = tmp_path / "data" / "field_returns" / "2026-09-30"
    folder.mkdir(parents=True)
    (folder / "JPEG_1.jpg").write_bytes(b"jpg")
    cols = ", ".join(f"{c} TEXT" for c in qfield.SCORES)
    with sqlite3.connect(folder / "field_check.gpkg") as c:
        c.execute(f"CREATE TABLE field_check (asset_id TEXT, tree_no INT, geom BLOB, {cols})")
        blank = {s: None for s in qfield.SCORES}
        for asset, no, extra in [
            ("PK1", 1, {"found": "found", "photo": "DCIM/JPEG_1.jpg", "notes": " ok  "}),
            ("PK2", 2, {"found": "missing"}),
            ("PK3", 3, {}),
        ]:
            row = {**blank, **extra, "asset_id": asset, "tree_no": no, "geom": gp(1)}
            c.execute(
                f"INSERT INTO field_check ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                list(row.values()),
            )
    return folder


def test_read_returns_skips_unvisited(returned):
    rows = qfield.read_returns(returned)
    assert [r["asset_id"] for r in rows] == ["PK1", "PK2"]


def test_read_returns_cleans_fields(returned):
    first = qfield.read_returns(returned)[0]
    assert first["geom"] == POINT
    assert first["notes"] == "ok"
    assert first["photo"] == "data/field_returns/2026-09-30/JPEG_1.jpg"
