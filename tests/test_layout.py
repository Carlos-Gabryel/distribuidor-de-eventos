from ui.layout import grid_extent, use_mobile


def test_use_mobile():
    assert use_mobile(True, 1200) and use_mobile(True, None)
    assert use_mobile(False, 500) and not use_mobile(False, 1180)
    assert not use_mobile(False, 0) and not use_mobile(False, None)


def test_grid_extent_smaller_on_mobile():
    assert grid_extent(True) < grid_extent(False) == 160
