# -*- coding: utf-8 -*-
"""#3317: changing the Vault Tail lower fold must not change other EndCaps.

Baseline source, original CUTTING, and existing Family policies remain owner.
All assertions are Engine/preview invariants, not manufacturing release.
"""
from __future__ import annotations

import pytest

from ae_engine import ae
from ae_engine import manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.manufacturing_render_data import material_polygon_from_final_scene
from ae_engine.sheetmetal_drawing import PolylinePrimitive


def _spec(*, family="金庫型", is_tail=True, bottom=15.):
    return EndCapPartSpec(
        width=620., depth=185., thickness=2., frame_width=25.,
        height=600., model_name=family, is_tail=is_tail,
        fold_left=15., fold_right=15., fold_top=16.,
        fold_bottom=bottom,
    )


def _render_with_stretched_call_record(spec, monkeypatch):
    real = ae._build_stretched_end_cap_scene
    kwargs_seen = []

    def record(*args, **kwargs):
        kwargs_seen.append(dict(kwargs))
        return real(*args, **kwargs)

    with monkeypatch.context() as mp:
        mp.setattr(ae, "_build_stretched_end_cap_scene", record)
        scene = api.build_part_scene(spec)
    return scene, kwargs_seen


def _bbox(scene):
    return material_polygon_from_final_scene(scene).bounds


def _square_bbox(scene):
    origin = ae.VAULT_ENDCAP_FEATURE_POLICY.square_hole_origin
    size = ae.VAULT_ENDCAP_FEATURE_POLICY.square_hole_size
    expected = (origin.x, origin.y, origin.x + size.x, origin.y + size.y)
    matches = []
    for row in scene.primitives:
        if (not isinstance(row, PolylinePrimitive)
                or row.layer != "CUTTING" or not row.closed
                or len(row.points) != 4):
            continue
        bbox = (
            min(v.x for v in row.points), min(v.y for v in row.points),
            max(v.x for v in row.points), max(v.y for v in row.points),
        )
        if all(abs(a - b) <= 1e-7 for a, b in zip(bbox, expected)):
            matches.append(row)
    assert len(matches) == 1
    return expected


def test_untouched_vault_tail_retains_legacy_baseline_and_square(monkeypatch):
    spec = _spec(is_tail=True, bottom=ae.ybottom1_def)
    raw, seen = _render_with_stretched_call_record(spec, monkeypatch)
    assert len(seen) == 1
    assert all(not k.startswith("target_fold_") for k in seen[0])
    legacy = ae._build_stretched_end_cap_scene(
        "金庫型", 620., 600., 185., 2., 25., is_tail=True,
    ).scene
    assert _bbox(raw) == pytest.approx(_bbox(legacy))
    assert material_polygon_from_final_scene(raw).symmetric_difference(
        material_polygon_from_final_scene(legacy)
    ).area < 1e-6
    assert _square_bbox(raw) == _square_bbox(legacy)


def test_unrelated_vault_head_with_48mm_lower_draft_uses_prior_stretched_source(monkeypatch):
    # Head Y profile must NOT be silently remodeled by a Tail-only fix,
    # even when its own PartSpec happens to carry the same 48mm number.
    spec = _spec(is_tail=False, bottom=48.)
    raw, seen = _render_with_stretched_call_record(spec, monkeypatch)
    assert len(seen) == 1
    assert all(not k.startswith("target_fold_") for k in seen[0])
    legacy = ae._build_stretched_end_cap_scene(
        "金庫型", 620., 600., 185., 2., 25., is_tail=False,
    ).scene
    assert _bbox(raw) == pytest.approx(_bbox(legacy))
    assert material_polygon_from_final_scene(raw).symmetric_difference(
        material_polygon_from_final_scene(legacy)
    ).area < 1e-6
    assert _bbox(raw)[3] == pytest.approx(235.)


def test_unrelated_receiving_endcap_never_receives_vault_tail_fold_override(monkeypatch):
    for is_tail in (True, False):
        spec = _spec(family="受電箱", is_tail=is_tail, bottom=48.)
        scene, seen = _render_with_stretched_call_record(spec, monkeypatch)
        assert scene.primitives
        assert all(
            not any(k.startswith("target_fold_") for k in options)
            for options in seen
        )
        assert not material_polygon_from_final_scene(scene).is_empty


def test_changed_vault_tail_only_overrides_real_lower_fold_and_fixed_square(monkeypatch):
    spec = _spec(is_tail=True, bottom=48.)
    raw, seen = _render_with_stretched_call_record(spec, monkeypatch)
    assert len(seen) == 1
    forwarded = {k: v for k, v in seen[0].items() if k.startswith("target_fold_")}
    assert forwarded == {"target_fold_bottom": pytest.approx(48.)}
    assert _bbox(raw) == pytest.approx((0., 0., 642., 268.))
    assert _square_bbox(raw) == pytest.approx((3., 18., 7., 22.))
