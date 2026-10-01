import pytest

from beech import crown_indices as ci


def bands(scale=0.0001, offset=-0.1, odd=None):
    b = {k: {"scale": scale, "offset": offset} for k in ci.REFLECTANCE_BANDS}
    b["scl"] = {"scale": 1, "offset": 0}
    if odd:
        b[odd]["scale"] = 0.001
    return b


def test_scene_entry_uses_offset_in_files_not_catalogue():
    s = ci.scene_entry("S2A_X", bands())
    assert s["offset"] == ci.OFFSET_IN_FILES == 0
    assert s["catalogue_offset"] == -0.1
    assert s["scale"] == 0.0001


def test_scene_entry_has_every_band_path():
    s = ci.scene_entry("S2A_X", bands())
    assert set(s["bands"]) == {"red", "nir", "nir08", "rededge1", "swir16", "scl"}
    assert s["bands"]["scl"].endswith("S2A_X\\scl.tif") or s["bands"]["scl"].endswith("S2A_X/scl.tif")


def test_scene_entry_rejects_mixed_scales():
    with pytest.raises(ValueError):
        ci.scene_entry("S2A_X", bands(odd="swir16"))


def test_obs_rows_parse_fractional_counts_and_nulls(tmp_path):
    f = tmp_path / "S2A_X.csv"
    f.write_text(
        "asset_id,clear_count,clear_mean,ndvi_count,ndvi_mean,ndmi_mean,ndre_mean\n"
        "PK1,1.038,1,1.038,0.86,0.25,0.53\n"
        "PK2,3,0,,,,\n"
    )
    rows = list(ci.obs_rows(f))
    assert rows[0] == ("S2A_X", "PK1", 1.038, 1.0, 1.038, 0.86, 0.25, 0.53)
    assert rows[1] == ("S2A_X", "PK2", 3.0, 0.0, None, None, None, None)
