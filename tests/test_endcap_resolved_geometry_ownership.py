# -*- coding: utf-8 -*-
"""EndCap resolved-geometry ownership contracts.

These tests protect the approved Phase6 boundary:
CornerType/Fold Profile are resolved once by AE; GUI/render/export consumers do not
recompute EndCap manufacturing spans.
"""
from __future__ import annotations

import pytest

from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    FourCornerTypePolicy,
    GeometryError,
    resolve_endcap_assembly_semantics,
    resolve_endcap_policy_assembly_semantics,
)


@pytest.mark.parametrize(
    ("type_id", "x_topology", "has_outer_fold", "factor"),
    [
        (CornerTypeId.INSERT, "folded", True, 0.0),
        (CornerTypeId.OVERLAY, "flat", False, 1.0),
        (CornerTypeId.INSERT_OVERLAY, "folded", True, 1.0),
    ],
)
def test_endcap_assembly_semantics_are_derived_from_corner_type(
    type_id, x_topology, has_outer_fold, factor,
):
    got = resolve_endcap_assembly_semantics(CornerTypeSelection(type_id))
    assert got.type_id is type_id
    assert got.x_topology == x_topology
    assert got.has_box_side_outer_fold is has_outer_fold
    assert got.outer_thickness_factor == pytest.approx(factor)


def test_endcap_policy_rejects_mixed_top_assembly_types():
    policy = FourCornerTypePolicy(
        bottom_left=CornerTypeSelection(CornerTypeId.CROSS),
        bottom_right=CornerTypeSelection(CornerTypeId.CROSS),
        top_left=CornerTypeSelection(CornerTypeId.OVERLAY),
        top_right=CornerTypeSelection(CornerTypeId.INSERT),
        fw=25.0,
    )
    with pytest.raises(GeometryError):
        resolve_endcap_policy_assembly_semantics(policy)

from ae_engine.contracts import EndCapPartSpec, FoldProfileSegment
from ae_engine.manufacturing_api import resolve_endcap_request


def _seg(length, angle=None, core=None, key=None):
    return FoldProfileSegment(
        length=float(length), angle=angle, core=core, phase6_key=key
    )


def test_resolved_endcap_request_uses_profile_before_scalar_folds():
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=91, fold_right=92, fold_top=93, fold_bottom=94,
        fold_profile_x=(
            _seg(10, -90, key="left"),
            _seg(392, -90, core="W-2T", key="endcap_w_core"),
            _seg(20, key="right"),
        ),
        fold_profile_y=(
            _seg(7, -90, key="front_extra"),
            _seg(25, -90, key="fw"),
            _seg(244, -90, core="D-T", key="endcap_d_core"),
            _seg(13, key="ybottom1"),
        ),
    )
    got = resolve_endcap_request(spec)
    assert (got.fold_left, got.fold_right, got.fold_top, got.fold_bottom) == pytest.approx((10, 20, 7, 13))



def test_resolved_endcap_request_normalizes_corner_policy_fw_to_profile_material_space():
    top = CornerTypeSelection(CornerTypeId.INSERT_OVERLAY)
    bottom = CornerTypeSelection(CornerTypeId.CROSS)
    # Receiving UI carries operator FW=29, while Fold Profile is already material space FW=25.
    # Corner policy used by manufacturing CUTTING must follow the material Fold Profile,
    # otherwise raw EndCap relief is cut as 44×47 and conflicts with the certified 40×39 rule.
    policy = FourCornerTypePolicy(bottom, bottom, top, top, fw=29.0, bottom_fw=17.0)
    spec = EndCapPartSpec(
        width=800, depth=350, height=1600, thickness=2, frame_width=29,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(
            _seg(15, -90, key="yl1"),
            _seg(792, -90, core="W-2T", key="endcap_w_core"),
            _seg(15, key="yr1"),
        ),
        fold_profile_y=(
            _seg(16, -90, key="ytop1"),
            _seg(25, -90, key="fw"),
            _seg(346, -90, core="D-2T", key="endcap_d_core"),
            _seg(15, key="ybottom1"),
        ),
        corner_policy=policy,
        depth_comp_t=2.0,
    )

    got = resolve_endcap_request(spec)

    assert got.frame_width == pytest.approx(25.0)
    assert got.corner_policy is not None
    assert got.corner_policy.fw == pytest.approx(25.0)
    assert got.corner_policy.bottom_fw == pytest.approx(17.0)

def test_flat_x_profile_forces_zero_effective_side_folds_without_guessing_corner_type():
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(_seg(400, key="endcap_w_flat"),),
    )
    got = resolve_endcap_request(spec)
    assert got.assembly is None
    assert got.fold_left == pytest.approx(0)
    assert got.fold_right == pytest.approx(0)


def test_overlay_corner_policy_forces_flat_x_even_with_legacy_scalar_folds():
    top = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.0)
    bottom = CornerTypeSelection(CornerTypeId.CROSS)
    policy = FourCornerTypePolicy(bottom, bottom, top, top, 25.0)
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        corner_policy=policy,
    )
    got = resolve_endcap_request(spec)
    assert got.assembly is not None
    assert got.assembly.type_id is CornerTypeId.OVERLAY
    assert got.assembly.x_topology == "flat"
    assert (got.fold_left, got.fold_right) == pytest.approx((0, 0))


def test_build_part_render_data_consumes_resolved_flat_x_request():
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import build_part_render_data

    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(_seg(400, key="endcap_w_flat"),),
    )
    render = build_part_render_data(spec, ManufacturingContext(draw_stock=False))
    minx, _miny, maxx, _maxy = map(float, render.material.bounds)
    assert maxx - minx == pytest.approx(400)


def test_resolved_endcap_request_uses_legacy_scalars_without_profiles():
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=11, fold_right=12, fold_top=13, fold_bottom=14,
    )
    got = resolve_endcap_request(spec)
    assert (got.fold_left, got.fold_right, got.fold_top, got.fold_bottom) == pytest.approx((11, 12, 13, 14))
    assert got.x_topology == "folded"


def test_gui_endcap_adapter_does_not_pre_resolve_profile_into_scalar_folds():
    import gui

    app = object.__new__(gui.BoxCalculatorGUI)
    spec = app._end_cap_part_spec_from_values(
        {
            "w": 400, "h": 600, "d": 250, "t": 2, "fw": 25,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "zl1": 20, "zr1": 21,
        },
        model_name=None,
        is_tail=False,
        holes=(),
        fold_profiles={
            "X": [
                {"len": 10, "angle": -90, "phase6_key": "left"},
                {"len": 392, "angle": -90, "core": "W-2T", "phase6_key": "endcap_w_core"},
                {"len": 20, "phase6_key": "right"},
            ],
            "Y": [
                {"len": 7, "angle": -90, "phase6_key": "front_extra"},
                {"len": 25, "angle": -90, "phase6_key": "fw"},
                {"len": 244, "angle": -90, "core": "D-T", "phase6_key": "endcap_d_core"},
                {"len": 13, "phase6_key": "ybottom1"},
            ],
        },
    )
    assert (spec.fold_left, spec.fold_right, spec.fold_top, spec.fold_bottom) == pytest.approx((15, 15, 16, 15))
    assert len(spec.fold_profile_x) == 3
    assert len(spec.fold_profile_y) == 4


def test_gui_endcap_adapter_resolves_receiving_depth_compensation_from_family_when_omitted():
    import gui

    app = object.__new__(gui.BoxCalculatorGUI)
    spec = app._end_cap_part_spec_from_values(
        {
            "w": 800, "h": 1600, "d": 350, "t": 2, "fw": 29,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "zl1": 24, "zr1": 17,
        },
        model_name="受電箱",
        is_tail=False,
        holes=(),
    )
    assert spec.depth_comp_t == pytest.approx(2.0)


def _overlay_policy():
    from ae_engine.sheetmetal_geometry import CornerDirection, CrossCornerMode

    top = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.0)
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.WIDTH,
        amount_t=1.5,
    )
    return FourCornerTypePolicy(bottom, bottom, top, top, 25.0)


def test_overlay_corner_semantic_discards_stale_folded_x_profile_bends():
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import build_part_render_data

    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(
            _seg(15, -90, key="yl1"),
            _seg(392, -90, core="W-2T", key="endcap_w_core"),
            _seg(15, key="yr1"),
        ),
        fold_profile_y=(
            _seg(16, -90, key="ytop1"),
            _seg(25, -90, key="fw"),
            _seg(244, -90, core="D-T", key="endcap_d_core"),
            _seg(15, key="ybottom1"),
        ),
        corner_policy=_overlay_policy(),
    )
    resolved = resolve_endcap_request(spec)
    assert resolved.x_topology == "flat"
    assert resolved.fold_profile_x == ()

    render = build_part_render_data(spec, ManufacturingContext(draw_stock=False))
    vertical_bends = [
        primitive for primitive in render.scene.primitives
        if str(getattr(primitive, "layer", "")).upper() == "BEND"
        and hasattr(primitive, "p1") and hasattr(primitive, "p2")
        and abs(float(primitive.p1.x) - float(primitive.p2.x)) < 1e-9
    ]
    assert vertical_bends == []


@pytest.mark.parametrize("is_tail", [False, True])
def test_overlay_400_span_is_identical_from_resolver_to_dxf(tmp_path, is_tail):
    import ezdxf
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import build_part_render_data, save_part_render_data_dxf

    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        is_tail=is_tail,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(_seg(400, key="endcap_w_flat"),),
        fold_profile_y=(
            _seg(16, -90, key="ytop1"),
            _seg(25, -90, key="fw"),
            _seg(244, -90, core="D-T", key="endcap_d_core"),
            _seg(15, key="ybottom1"),
        ),
        corner_policy=_overlay_policy(),
    )

    resolved = resolve_endcap_request(spec)
    assert resolved.x_topology == "flat"
    assert (resolved.fold_left, resolved.fold_right) == pytest.approx((0, 0))

    render = build_part_render_data(spec, ManufacturingContext(draw_stock=False))
    minx, _miny, maxx, _maxy = map(float, render.material.bounds)
    assert maxx - minx == pytest.approx(400)

    vertical_bends = [
        primitive for primitive in render.scene.primitives
        if str(getattr(primitive, "layer", "")).upper() == "BEND"
        and hasattr(primitive, "p1") and hasattr(primitive, "p2")
        and abs(float(primitive.p1.x) - float(primitive.p2.x)) < 1e-9
    ]
    assert vertical_bends == []

    output = tmp_path / ("tail.dxf" if is_tail else "head.dxf")
    save_part_render_data_dxf(render, output, overwrite=True)
    doc = ezdxf.readfile(output)
    cutting = [
        ent for ent in doc.modelspace()
        if str(ent.dxf.layer).upper() == "CUTTING" and ent.dxftype() == "LWPOLYLINE"
    ]
    assert cutting
    points = [(float(x), float(y)) for x, y, *_ in cutting[0].get_points()]
    xs = [point[0] for point in points]
    assert max(xs) - min(xs) == pytest.approx(400)


def test_generate_part_endcap_uses_same_resolver_validation_without_profiles(tmp_path):
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import build_part_render_data, generate_part

    bottom = CornerTypeSelection(CornerTypeId.CROSS)
    mixed_policy = FourCornerTypePolicy(
        bottom_left=bottom,
        bottom_right=bottom,
        top_left=CornerTypeSelection(CornerTypeId.OVERLAY),
        top_right=CornerTypeSelection(CornerTypeId.INSERT),
        fw=25.0,
    )
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        corner_policy=mixed_policy,
    )

    with pytest.raises(GeometryError):
        build_part_render_data(spec, ManufacturingContext(draw_stock=False))
    with pytest.raises(GeometryError):
        generate_part(spec, tmp_path / "mixed-endcap.dxf", ManufacturingContext(draw_stock=False))


def test_flat_x_only_profile_replaces_x_bends_but_preserves_existing_y_bends():
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import build_part_render_data

    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(_seg(400, key="endcap_w_flat"),),
    )
    render = build_part_render_data(spec, ManufacturingContext(draw_stock=False))
    bends = [
        primitive for primitive in render.scene.primitives
        if str(getattr(primitive, "layer", "")).upper() == "BEND"
        and hasattr(primitive, "p1") and hasattr(primitive, "p2")
    ]
    vertical = [
        primitive for primitive in bends
        if abs(float(primitive.p1.x) - float(primitive.p2.x)) < 1e-9
    ]
    horizontal = [
        primitive for primitive in bends
        if abs(float(primitive.p1.y) - float(primitive.p2.y)) < 1e-9
    ]
    assert vertical == []
    assert len(horizontal) >= 2


def test_endcap_outer_height_factor_uses_same_policy_semantics_and_rejects_mixed_top_types():
    from ae_engine.sheetmetal_geometry import endcap_outer_thickness_factor

    policy = FourCornerTypePolicy(
        bottom_left=CornerTypeSelection(CornerTypeId.CROSS),
        bottom_right=CornerTypeSelection(CornerTypeId.CROSS),
        top_left=CornerTypeSelection(CornerTypeId.OVERLAY),
        top_right=CornerTypeSelection(CornerTypeId.INSERT),
        fw=25.0,
    )
    with pytest.raises(GeometryError):
        endcap_outer_thickness_factor(policy)


def test_unknown_endcap_scene_receives_resolved_x_topology(monkeypatch):
    from ae_engine.contracts import ManufacturingContext
    from ae_engine import manufacturing_api
    from ae_engine.sheetmetal_drawing import DrawingScene

    captured = {}

    def fake_unknown_builder(*, x_topology, **kwargs):
        captured["x_topology"] = x_topology
        return DrawingScene()

    monkeypatch.setattr(manufacturing_api, "_baseline_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(manufacturing_api.ae, "_build_unknown_end_cap_scene", fake_unknown_builder)

    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        corner_policy=_overlay_policy(),
    )
    manufacturing_api.build_part_scene(spec, ManufacturingContext(draw_stock=False))
    assert captured["x_topology"] == "flat"


def test_stretched_endcap_scene_receives_resolved_x_topology(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from ae_engine.contracts import ManufacturingContext
    from ae_engine import manufacturing_api
    from ae_engine.sheetmetal_drawing import DrawingScene

    captured = {}

    def fake_stretched_builder(model_name, width, height, depth, thickness, frame_width, *, x_topology, **kwargs):
        captured["x_topology"] = x_topology
        return SimpleNamespace(scene=DrawingScene())

    fake_baseline = tmp_path / "封頭尾.dxf"
    fake_baseline.write_bytes(b"fixture")
    monkeypatch.setattr(manufacturing_api, "_baseline_path", lambda *args, **kwargs: fake_baseline)
    monkeypatch.setattr(manufacturing_api.ae, "_build_stretched_end_cap_scene", fake_stretched_builder)

    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        model_name="TEST",
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        corner_policy=_overlay_policy(),
    )
    manufacturing_api.build_part_scene(spec, ManufacturingContext(draw_stock=False))
    assert captured["x_topology"] == "flat"


def test_stretched_flat_endcap_reports_effective_zero_x_folds(monkeypatch, tmp_path):
    from ae_engine import ae

    baseline = tmp_path / "封頭尾.dxf"
    ae.export_end_cap_dxf(
        baseline,
        W_val=400, H_val=600, D_val=250, T_val=2, FW_val=25,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        draw_stock=False, is_tail=True, holes=(),
    )
    monkeypatch.setattr(ae, "baseline_part_path", lambda *args, **kwargs: str(baseline))

    data = ae.get_stretched_end_cap_data(
        "TEST", 400, 600, 250, 2, 25, True, _overlay_policy(), "flat"
    )
    assert data.params["total_width"] == pytest.approx(400)
    assert data.params["yl1"] == pytest.approx(0)
    assert data.params["yr1"] == pytest.approx(0)


def test_insert_corner_semantic_discards_stale_flat_x_profile_and_keeps_folded_scalars():
    top = CornerTypeSelection(CornerTypeId.INSERT)
    bottom = CornerTypeSelection(CornerTypeId.CROSS)
    policy = FourCornerTypePolicy(bottom, bottom, top, top, 25.0)
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        fold_left=15, fold_right=16, fold_top=16, fold_bottom=15,
        fold_profile_x=(_seg(400, key="endcap_w_flat"),),
        corner_policy=policy,
    )
    got = resolve_endcap_request(spec)
    assert got.assembly is not None
    assert got.assembly.x_topology == "folded"
    assert got.x_topology == "folded"
    assert got.fold_profile_x == ()
    assert (got.fold_left, got.fold_right) == pytest.approx((15, 16))
