import json

import pytest

from beech.sentinel import BANDS, item_to_row, search_items


def _asset(offset):
    return {
        "href": "https://example/B04.tif",
        "raster:bands": [{"scale": 0.0001, "offset": offset, "nodata": 0,
                          "spatial_resolution": 10}],
    }


def _item(offset=0.0, bands=BANDS):
    return {
        "id": "S2B_30UWC_20230715_0_L2A",
        "collection": "sentinel-2-l2a",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        "properties": {
            "datetime": "2023-07-15T11:16:57Z",
            "platform": "sentinel-2b",
            "grid:code": "MGRS-30UWC",
            "eo:cloud_cover": 12.5,
            "s2:processing_baseline": "05.09",
            "earthsearch:boa_offset_applied": True,
        },
        "assets": {b: _asset(offset) for b in bands},
    }


def test_item_to_row_keeps_scale_and_offset_per_band():
    row = item_to_row(_item(offset=-0.1))
    bands = json.loads(row["bands"])
    assert set(bands) == set(BANDS)
    assert bands["red"]["scale"] == 0.0001
    assert bands["red"]["offset"] == -0.1  # the post-2022 offset is recorded
    assert row["mgrs_tile"] == "MGRS-30UWC"


def test_item_without_raster_metadata_defaults_to_no_offset():
    item = _item()
    item["assets"]["scl"] = {"href": "https://example/SCL.tif"}
    bands = json.loads(item_to_row(item)["bands"])
    assert (bands["scl"]["scale"], bands["scl"]["offset"]) == (1, 0)


def test_item_missing_a_band_is_rejected():
    with pytest.raises(ValueError):
        item_to_row(_item(bands=("red", "nir")))


class _FakeSession:
    """Two pages; the first carries a 'next' token in its link body."""

    def __init__(self):
        self.bodies = []

    def post(self, url, json, timeout):
        self.bodies.append(json)
        page = len(self.bodies)
        payload = {"features": [{"id": f"item{page}"}], "links": []}
        if page == 1:
            payload["links"] = [{"rel": "next", "body": {"next": "token-2"}}]

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        return R()


def test_search_follows_next_links():
    s = _FakeSession()
    ids = [f["id"] for f in search_items(s, {"type": "Point"}, "2018-01-01", "2018-12-31")]
    assert ids == ["item1", "item2"]
    assert s.bodies[1]["next"] == "token-2"
    assert s.bodies[1]["collections"] == ["sentinel-2-l2a"]  # rest of body kept


def test_translate_args_window_in_bng_and_reads_from_cloud():
    from pathlib import Path

    from beech.s2_download import translate_args

    args = translate_args("https://x/B04.tif", Path("out.tif"), (1, 2, 3, 4))
    i = args.index("-projwin")
    assert args[i + 1 : i + 5] == ["1", "4", "3", "2"]  # ulx uly lrx lry
    assert args[args.index("-projwin_srs") + 1] == "EPSG:27700"
    assert "/vsicurl/https://x/B04.tif" in args
