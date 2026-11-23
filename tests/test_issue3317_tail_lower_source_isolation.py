# -*- coding: utf-8 -*-
"""#3317: the authored Tail lower station must not affect other EndCaps."""
import pytest
from ae_engine import ae
from ae_engine import manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.manufacturing_render_data import material_polygon_from_final_scene


def _part(*, model="金庫型", is_tail=True, bottom=None):
    return EndCapPartSpec(
        width=620., depth=185., height=600., thickness=2.,
        frame_width=25., model_name=model, is_tail=is_tail,
        fold_left=15., fold_right=15., fold_top=16., fold_bottom=bottom,
    )


def _call(spec, monkeypatch):
    real = ae._build_stretched_end_cap_scene
    seen = []
    def record(*args, **kwargs):
        seen.append(kwargs)
        return real(*args, **kwargs)
    with monkeypatch.context() as mp:
        mp.setattr(ae, "_build_stretched_end_cap_scene", record)
        scene = api.build_part_scene(spec)
    return material_polygon_from_final_scene(scene), seen


@pytest.mark.parametrize("model,is_tail,bottom,should_override", [
    ("金庫型", True, None, False),
    ("金庫型", True, 48., True),
    ("金庫型", False, 48., False),
    ("受電箱", True, 48., False),
    ("受電箱", False, 48., False),
])
def test_only_authored_vault_tail_lower_fold_is_forwarded(
    monkeypatch, model, is_tail, bottom, should_override,
):
    material, seen = _call(_part(model=model, is_tail=is_tail, bottom=bottom), monkeypatch)
    assert not material.is_empty
    assert len(seen) == 1
    forwarded = {k: v for k, v in seen[0].items() if k.startswith("target_fold_")}
    if should_override:
        assert forwarded == {"target_fold_bottom": pytest.approx(bottom)}
    else:
        assert forwarded == {}


def test_authored_tail_lower_fold_ignores_mutable_startup_default(monkeypatch):
    snapshots = []
    for default in (15., 48.):
        with monkeypatch.context() as mp:
            mp.setattr(ae, "ybottom1_def", default)
            material, _ = _call(_part(bottom=48.), mp)
            snapshots.append(material)
    assert snapshots[0].symmetric_difference(snapshots[1]).area < 1e-7
