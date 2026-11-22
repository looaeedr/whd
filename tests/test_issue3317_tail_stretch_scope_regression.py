# -*- coding: utf-8 -*-
"""#3317 Tail lower-fold source override must never change other EndCaps.

Compare the public manufacturing path with the pre-existing unstretched-target
baseline scene for unchanged Tail, Head and Receiving. Negative variants
intentionally carry an explicit 48-mm fold to catch accidental shared routing.
"""
from dataclasses import replace
import pytest

from ae_engine import ae
from ae_engine import manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.manufacturing_render_data import material_polygon_from_final_scene
from ae_engine.sheetmetal_drawing import PolylinePrimitive


def _spec(*, model="金庫型", is_tail=True, bottom=None):
    return EndCapPartSpec(
        width=620., depth=185., thickness=2., frame_width=25.,
        height=600., model_name=model, is_tail=is_tail,
        fold_left=15., fold_right=15., fold_top=16., fold_bottom=bottom,
        box_fold_left=15., box_fold_right=15.,
    )


def _baseline_without_tail_override(spec):
    return ae._build_stretched_end_cap_scene(
        spec.model_name, spec.width, spec.height, spec.depth,
        spec.thickness, spec.frame_width, is_tail=spec.is_tail,
    ).scene


@pytest.mark.parametrize("name,spec", (
    ("untouched_vault_tail", _spec()),
    ("vault_head_explicit_48", _spec(is_tail=False, bottom=48.)),
))
def test_non_target_stretched_endcaps_keep_original_raw_cutting_and_holes(name, spec):
    scene = api.build_part_scene(spec)
    baseline = _baseline_without_tail_override(spec)
    assert tuple(scene.primitives) == tuple(baseline.primitives), name
    actual = material_polygon_from_final_scene(scene)
    expected = material_polygon_from_final_scene(baseline)
    assert actual.symmetric_difference(expected).area < 1e-7, name
    assert actual.bounds[2] == pytest.approx(642.)
    assert actual.bounds[3] == pytest.approx(235.), name


def test_only_authored_vault_tail_48_resolves_to_268_with_fixed_square():
    spec = _spec(bottom=48.)
    scene = api.build_part_scene(spec)
    sheet = material_polygon_from_final_scene(scene)
    assert sheet.bounds[2] == pytest.approx(642.)
    assert sheet.bounds[3] == pytest.approx(268.)
    assert not sheet.equals(material_polygon_from_final_scene(
        _baseline_without_tail_override(spec)
    ))
    fixed = ae.VAULT_ENDCAP_FEATURE_POLICY
    expected_bbox = (
        fixed.square_hole_origin.x, fixed.square_hole_origin.y,
        fixed.square_hole_origin.x + fixed.square_hole_size.x,
        fixed.square_hole_origin.y + fixed.square_hole_size.y,
    )
    squares = [
        p for p in scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
        and p.closed and len(p.points) == 4
        and tuple(
            fn(v) for fn, v in (
                (min, (pt.x for pt in p.points)),
                (min, (pt.y for pt in p.points)),
                (max, (pt.x for pt in p.points)),
                (max, (pt.y for pt in p.points)),
            )
        ) == pytest.approx(expected_bbox)
    ]
    assert len(squares) == 1


def test_receiving_tail_does_not_enter_vault_tail_stretched_override(monkeypatch):
    # Receiving has no direct 封頭尾.dxf at this repository path. Compare the
    # real canonical Engine result and ensure the Vault-only baseline adapter
    # is not invoked. Never synthesize a nonexistent Receiving baseline.
    spec = _spec(model="受電箱", bottom=48.)
    def no_stretched(*_args, **_kwargs):
        pytest.fail("RECEIVING_MUST_NOT_USE_VAULT_STRETCHED_ENDCAP")
    with monkeypatch.context() as mp:
        mp.setattr(ae, "_build_stretched_end_cap_scene", no_stretched)
        scene = api.build_part_scene(spec)
    actual = material_polygon_from_final_scene(scene)
    assert actual.is_valid and actual.area > 0
