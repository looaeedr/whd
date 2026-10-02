import math

import pytest

from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    ReliefConfig,
    corner_type_residual,
    resolve_corner_relief,
)
from ae_engine.sheetmetal_part_adapters import (
    build_base_plate_result,
    build_door_result,
    build_endcap_result,
    build_indicator_box_result,
)


def _outline(result):
    return [(round(p.x, 6), round(p.y, 6)) for p in result.outline]


def _bends(result):
    return [
        (
            b.name,
            (round(b.p1.x, 6), round(b.p1.y, 6)),
            (round(b.p2.x, 6), round(b.p2.y, 6)),
        )
        for b in result.bends
    ]


def test_corner_type_residuals_are_fold_independent():
    t = 2.0
    fw = 25.0
    assert corner_type_residual(CornerTypeId.C01, thickness=t, fw=fw).primary == (0.0, 0.0)
    assert corner_type_residual(CornerTypeId.C02, thickness=t, fw=fw).primary == (-2.0, 0.0)
    assert corner_type_residual(CornerTypeId.C03, thickness=t, fw=fw).primary == (1.0, 1.0)

    c04 = corner_type_residual(CornerTypeId.C04, thickness=t, fw=fw)
    assert c04.primary == (25.0, 23.0)
    assert c04.secondary_u == 1.0
    assert c04.secondary_depth == 4.0


def test_c02_rotation_swaps_meat_axis_without_new_type():
    normal = resolve_corner_relief(
        CornerTypeSelection(CornerTypeId.C02, rotation_quadrants=0),
        fold_u=19.0,
        fold_v=15.0,
        thickness=2.0,
        fw=25.0,
    )
    rotated = resolve_corner_relief(
        CornerTypeSelection(CornerTypeId.C02, rotation_quadrants=1),
        fold_u=19.0,
        fold_v=15.0,
        thickness=2.0,
        fw=25.0,
    )
    assert normal.primary_u == 17.0
    assert normal.primary_v == 15.0
    assert rotated.primary_u == 19.0
    assert rotated.primary_v == 13.0


def test_vault_door_geometry_snapshot_is_unchanged():
    result = build_door_result(
        w=500, h=600, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
    )
    assert _outline(result) == [
        (17.0, 0.0), (452.0, 0.0), (452.0, 15.0), (465.0, 15.0),
        (465.0, 546.0), (452.0, 546.0), (452.0, 561.0), (17.0, 561.0),
        (17.0, 546.0), (0.0, 546.0), (0.0, 15.0), (17.0, 15.0), (17.0, 0.0),
    ]
    assert _bends(result) == [
        ('left', (19.0, 0.0), (19.0, 561.0)),
        ('right', (450.0, 0.0), (450.0, 561.0)),
        ('bottom', (17.0, 15.0), (452.0, 15.0)),
        ('top', (17.0, 546.0), (452.0, 546.0)),
    ]


def test_vault_base_plate_geometry_snapshot_is_unchanged():
    result = build_base_plate_result(
        w=500, h=600, t=2,
        shrink_top=55, shrink_bottom=55, shrink_left=55, shrink_right=55, bend=15,
    )
    assert _outline(result) == [
        (15.0, 0.0), (405.0, 0.0), (405.0, 15.0), (420.0, 15.0),
        (420.0, 505.0), (405.0, 505.0), (405.0, 520.0), (15.0, 520.0),
        (15.0, 505.0), (0.0, 505.0), (0.0, 15.0), (15.0, 15.0), (15.0, 0.0),
    ]


def test_vault_indicator_box_geometry_snapshot_is_unchanged():
    result = build_indicator_box_result(total_width=416, total_height=445, t=2, fold=49)
    assert _outline(result) == [
        (47.0, 0.0), (369.0, 0.0), (369.0, 49.0), (416.0, 49.0),
        (416.0, 396.0), (369.0, 396.0), (369.0, 445.0), (47.0, 445.0),
        (47.0, 396.0), (0.0, 396.0), (0.0, 49.0), (47.0, 49.0), (47.0, 0.0),
    ]


def test_vault_endcap_geometry_snapshot_is_unchanged():
    result = build_endcap_result(
        w=500, d=150, t=2, fw=25,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        relief_config=ReliefConfig(),
    )
    assert _outline(result) == [
        (16.0, 0.0), (506.0, 0.0), (506.0, 16.0), (522.0, 16.0),
        (522.0, 157.0), (506.0, 157.0), (506.0, 161.0), (482.0, 161.0),
        (482.0, 200.0), (40.0, 200.0), (40.0, 161.0), (16.0, 161.0),
        (16.0, 157.0), (0.0, 157.0), (0.0, 16.0), (16.0, 16.0), (16.0, 0.0),
    ]
    assert _bends(result) == [
        ('left', (15.0, 16.0), (15.0, 157.0)),
        ('right', (507.0, 16.0), (507.0, 157.0)),
        ('bottom', (16.0, 15.0), (506.0, 15.0)),
        ('top_chain_1', (16.0, 159.0), (506.0, 159.0)),
        ('top_chain_2', (40.0, 184.0), (482.0, 184.0)),
    ]


def _manual_policy(bl, br, tl, tr, fw=25.0):
    from ae_engine.sheetmetal_geometry import FourCornerTypePolicy
    return FourCornerTypePolicy(
        bottom_left=CornerTypeSelection(bl),
        bottom_right=CornerTypeSelection(br),
        top_left=CornerTypeSelection(tl),
        top_right=CornerTypeSelection(tr),
        fw=fw,
    )


def test_unknown_door_can_reproduce_vault_c02_without_changing_vault_builder():
    from ae_engine.sheetmetal_part_adapters import build_unknown_door_result
    manual = build_unknown_door_result(
        w=500, h=600, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
        corner_policy=_manual_policy(CornerTypeId.C02, CornerTypeId.C02, CornerTypeId.C02, CornerTypeId.C02),
    )
    vault = build_door_result(
        w=500, h=600, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
    )
    assert _outline(manual) == _outline(vault)
    assert _bends(manual) == _bends(vault)


def test_unknown_endcap_c03_c04_can_reproduce_vault_default_geometry():
    from ae_engine.sheetmetal_part_adapters import build_unknown_endcap_result
    manual = build_unknown_endcap_result(
        w=500, d=150, t=2, fw=25, yl1=15, yr1=15, ytop1=16, ybottom1=15,
        corner_policy=_manual_policy(CornerTypeId.C03, CornerTypeId.C03, CornerTypeId.C04, CornerTypeId.C04),
        x_topology="folded",
    )
    vault = build_endcap_result(
        w=500, d=150, t=2, fw=25, yl1=15, yr1=15, ytop1=16, ybottom1=15,
        relief_config=ReliefConfig(),
    )
    assert _outline(manual) == _outline(vault)
    assert _bends(manual) == _bends(vault)


def test_unknown_c02_rotation_can_make_y_meat_without_new_corner_type():
    from ae_engine.sheetmetal_geometry import FourCornerTypePolicy
    from ae_engine.sheetmetal_part_adapters import build_unknown_door_result
    rotated_c02 = CornerTypeSelection(CornerTypeId.C02, rotation_quadrants=1)
    policy = FourCornerTypePolicy(rotated_c02, rotated_c02, rotated_c02, rotated_c02, fw=25.0)
    result = build_unknown_door_result(
        w=500, h=600, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
        corner_policy=policy,
    )
    # Rotation swaps -1T from local U (X) to local V (Y).
    assert (19.0, 0.0) in _outline(result)
    assert (0.0, 13.0) in _outline(result)
