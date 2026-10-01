from beech.lidar import LAYERS, TILE_M, coverage_url, tile_path


def test_coverage_url_requests_one_square_in_bng():
    url = coverage_url("dtm", 358000, 174000)
    assert "subset=E(358000,359000)" in url
    assert "subset=N(174000,175000)" in url
    assert LAYERS["dtm"][1] in url
    assert "format=image/tiff" in url


def test_tile_names_carry_layer_and_corner():
    p = tile_path("dsm", 358000, 174000)
    assert p.name == "dsm_358000_174000.tif"
    assert p.parent.name == "dsm"


def test_tiles_are_one_kilometre():
    assert TILE_M == 1000


def test_ogr2ogr_args_clip_to_bbox_and_force_bng():
    from pathlib import Path

    from beech.ingest_os import ogr2ogr_args

    args = ogr2ogr_args(Path("ST_Building.shp"), "raw.os_buildings", (1, 2, 3, 4))
    assert args[args.index("-nln") + 1] == "raw.os_buildings"
    assert args[args.index("-a_srs") + 1] == "EPSG:27700"
    i = args.index("-spat")
    assert args[i + 1 : i + 5] == ["1", "2", "3", "4"]


def test_model_args_avoid_pipes_for_windows_batch_files():
    from pathlib import Path

    from beech.run_models import model_args

    args = model_args(Path("chm.tif"), Path("trees.gpkg"), Path("b.gpkg"), Path("out.gpkg"))
    assert not any("|" in a for a in args)
    assert "tree_crowns=out.gpkg" in args
    assert "min_height=5" in args
