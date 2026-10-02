from __future__ import annotations

from pathlib import Path
import shutil

import ezdxf
import pytest

from ae_engine.contracts import EndCapPartSpec
from ae_engine.sheetmetal_drawing import CirclePrimitive
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, FourCornerTypePolicy


def _policy(fw=29.0):
    bottom = CornerTypeSelection(CornerTypeId.CROSS)
    top = CornerTypeSelection(CornerTypeId.INSERT_OVERLAY)
    return FourCornerTypePolicy(bottom, bottom, top, top, fw=float(fw), bottom_fw=17.0)


def _spec(*, model='金庫型', tail=False, depth_comp_t=3.0):
    return EndCapPartSpec(
        width=800, height=1600, depth=350, thickness=2, frame_width=29,
        model_name=model, is_tail=tail,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        corner_policy=_policy(), depth_comp_t=depth_comp_t,
    )


def _baseline_holes(scene):
    return tuple(
        p for p in scene.primitives
        if isinstance(p, CirclePrimitive)
        and str(p.layer).upper() == 'CUTTING'
        and getattr(p, 'source_type', None) == 'baseline_endcap_hole'
    )


@pytest.mark.parametrize('tail', [False, True])
def test_vault_head_and_tail_expose_all_current_baseline_cutting_holes_as_features(tail):
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene
    root = Path(__file__).resolve().parents[1]
    scene = build_part_scene(_spec(tail=tail), ManufacturingContext(resource_root=root))
    holes = _baseline_holes(scene)
    # Three is smoke evidence for this baseline snapshot, not a production constant.
    assert len(holes) == 3
    assert len({h.source_id for h in holes}) == 3


def test_head_and_tail_keep_same_baseline_feature_identity_set():
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene
    root = Path(__file__).resolve().parents[1]
    ctx = ManufacturingContext(resource_root=root)
    head = _baseline_holes(build_part_scene(_spec(tail=False), ctx))
    tail = _baseline_holes(build_part_scene(_spec(tail=True), ctx))
    assert {h.source_id for h in head} == {h.source_id for h in tail}


@pytest.mark.parametrize('tail', [False, True])
def test_receiving_reuses_vault_endcap_baseline_features_without_replacing_receiving_geometry(tail):
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene, material_polygon_from_final_scene
    root = Path(__file__).resolve().parents[1]
    ctx = ManufacturingContext(resource_root=root)
    spec = _spec(model='受電箱', tail=tail, depth_comp_t=2.0)
    scene = build_part_scene(spec, ctx)
    holes = _baseline_holes(scene)
    assert len(holes) == 3
    # Receiving structural D-space remains its 2T contract: 16 + 29 + (350-4) + 15 = 406 here.
    material = material_polygon_from_final_scene(scene)
    assert material.bounds[3] - material.bounds[1] == pytest.approx(406.0)


def test_baseline_feature_parser_is_not_hardcoded_to_three_holes(tmp_path, monkeypatch):
    from ae_engine import ae
    root = Path(__file__).resolve().parents[1]
    source = root / '基準檔' / '金庫型' / '封頭尾.dxf'
    target = tmp_path / '封頭尾.dxf'
    shutil.copy2(source, target)
    doc = ezdxf.readfile(target)
    doc.modelspace().add_circle((261.0, 100.0), 2.0, dxfattribs={'layer': 'CUTTING'})
    doc.saveas(target)
    ae.clear_baseline_dxf_source_cache()
    monkeypatch.setattr(ae, 'baseline_part_path', lambda model, filename: str(target))
    monkeypatch.setattr(ae, 'baseline_expected_path', lambda model, filename: str(target))
    data = ae.get_stretched_end_cap_data(
        '金庫型', 800, 1600, 350, 2, 29, False, _policy(), 'folded',
        depth_comp_t=3.0, target_fold_left=15, target_fold_right=15,
        target_fold_top=16, target_fold_bottom=15,
    )
    assert len(_baseline_holes(data.scene)) == 4
