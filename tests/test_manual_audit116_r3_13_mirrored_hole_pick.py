"""Original 116 audit #45 / R3-13: mirrored 2D click must select the real physical hole.

Source-only regression.  A native Windows Tk mouse UAT and manufacturing signoff
remain separate.  This does not create or update a product coordinate formula.
"""

import pytest

from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_feature_core import ResolvedProfile
from ae_engine.sheetmetal_features import hit_test_resolved_features
from gui_modules.rendering.transforms import (
    YMirroredPreviewTransform, phase6_2d_material_viewport,
)


@pytest.mark.parametrize("canvas_size", ((600., 450.), (1000., 700.), (1400., 900.)))
def test_r3_13_mirrored_canvas_click_hits_correct_1100mm_upper_door_hole(canvas_size):
    """Real viewport + inverse transform + hit-test must agree after resizing.

    The two separated hole centers are mirror partners in the physical Door.
    A regression that drops the inverse Y mirror selects the opposite hole.
    """
    width, height = 723., 1100.
    points = (Vec2(200., 110.), Vec2(200., 990.))
    features = tuple(ResolvedProfile(points=(point,)) for point in points)
    base, *_ = phase6_2d_material_viewport((0., 0., width, height), *canvas_size)
    mirrored = YMirroredPreviewTransform(base, height=height)

    assert mirrored.scale == pytest.approx(base.scale)
    assert mirrored.height == height
    assert mirrored.world_to_canvas(points[0])[1] < mirrored.world_to_canvas(points[1])[1]

    for physical_index, point in enumerate(points):
        x_px, y_px = mirrored.world_to_canvas(point)
        recovered = mirrored.canvas_to_world(x_px, y_px)
        assert (recovered.x, recovered.y) == pytest.approx((point.x, point.y))
        assert hit_test_resolved_features(recovered, features, tolerance=1.) == physical_index

        # Anti-false-green witness: without the corrective inverse mirror, the
        # same click resolves the opposite physical row.
        wrong_world = base.canvas_to_world(x_px, y_px)
        assert hit_test_resolved_features(wrong_world, features, tolerance=1.) == 1 - physical_index
