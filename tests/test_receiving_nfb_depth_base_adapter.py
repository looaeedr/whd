# -*- coding: utf-8 -*-
"""#1502: real Receiving CENTER adapter uses selected NFB depth pair, no hardcode."""
import pytest

from ae_engine.sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_CENTER, RECEIVING_BASE_PATTERN_LEFT,
    build_receiving_base_plate_result,
)


def _base(**kwargs):
    values = dict(
        w=800, h=320, t=2, shrink_top=55, shrink_bottom=55,
        shrink_left=85, shrink_right=85, bend=20,
        pattern=RECEIVING_BASE_PATTERN_CENTER,
    )
    values.update(kwargs)
    return build_receiving_base_plate_result(**values)


def test_nfb_107_72_t2_produces_original_33_return_and_matching_real_bends():
    result = _base(nfb_depth_pair_mm=(107, 72))
    assert result.width == 772  # 630 + 2 * (40 + 33 - T2)
    assert result.height == 210
    assert {b.name for b in result.bends} == {
        "receiving_bottom_20", "receiving_top_20",
        "receiving_left_40", "receiving_left_33",
        "receiving_right_40", "receiving_right_33",
    }
    # Local 2D BEND station spacing is NOT an NFB face-to-face Z dimension.
    by_name = {b.name: b for b in result.bends}
    left_first = by_name["receiving_left_40"]
    left_second = by_name["receiving_left_33"]
    assert left_first.p1.x == 40
    assert left_second.p1.x == 71
    assert left_second.p1.x - left_first.p1.x == 31


def test_alternate_depths_change_base_material_outline_and_second_bend_station():
    result = _base(nfb_depth_pair_mm=(105, 75))
    assert result.width == 762  # 630 + 2 * (40 + 28 - T2)
    by_name = {b.name: b for b in result.bends}
    assert by_name["receiving_left_33"].p1.x == 66
    assert by_name["receiving_right_33"].p1.x == 762 - 66


def test_missing_depth_pair_preserves_explicit_unreleased_legacy_preview():
    # Legacy config can still show a physical pattern, but 33 here is NOT
    # proof that selected switch depths were checked or manufacturing ready.
    legacy = _base()
    verified_example = _base(nfb_depth_pair_mm=(107, 72))
    assert legacy.width == verified_example.width


def test_flat_sided_plate_never_needs_or_consumes_a_second_side_return():
    flat = _base(pattern=RECEIVING_BASE_PATTERN_LEFT)
    assert flat.width == 630
    assert len(flat.bends) == 2


@pytest.mark.parametrize("pair", [(107, 107), (72, 107), (107, 106), (107,),
                                  "107/72", (float("nan"), 72)])
def test_invalid_center_depth_pair_cannot_manufacture_an_invented_return(pair):
    with pytest.raises((ValueError, TypeError)):
        _base(nfb_depth_pair_mm=pair)
