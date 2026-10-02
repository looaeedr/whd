import pytest

from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    FourCornerTypePolicy,
    normalize_corner_selection,
    resolve_corner_relief,
    calculate_endcap_relief_dimensions,
    EndCapGeometry,
    ReliefConfig,
    resolve_endcap_assembly_semantics,
)
from ae_engine.sheetmetal_part_adapters import build_box_body_result, build_unknown_endcap_result
from ae_engine.corner_type_ui import (
    apply_manual_corner_selection,
    new_manual_corner_state,
)


def _policy(top_type: CornerTypeId, *, fw=25.0):
    cross = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH,
        amount_t=0.5,
    )
    top = CornerTypeSelection(top_type)
    return FourCornerTypePolicy(
        bottom_left=cross,
        bottom_right=cross,
        top_left=top,
        top_right=top,
        fw=fw,
    )


def _box(*, h=600.0, t=2.0, head=None, tail=None):
    return build_box_body_result(
        w=400.0, h=h, d=250.0, t=t, fw=25.0,
        zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=0.0,
        head_corner_policy=head, tail_corner_policy=tail,
    )


def test_legacy_corner_ids_normalize_to_new_manufacturing_semantics():
    c01 = normalize_corner_selection(CornerTypeSelection(CornerTypeId.C01))
    assert c01.type_id is CornerTypeId.CROSS
    assert c01.cross_mode is CrossCornerMode.STANDARD

    c02w = normalize_corner_selection(CornerTypeSelection(CornerTypeId.C02, 0))
    assert (c02w.type_id, c02w.cross_mode, c02w.direction, c02w.amount_t) == (
        CornerTypeId.CROSS, CrossCornerMode.RETAIN, CornerDirection.WIDTH, 1.0,
    )

    c02h = normalize_corner_selection(CornerTypeSelection(CornerTypeId.C02, 1))
    assert c02h.direction is CornerDirection.HEIGHT

    c03 = normalize_corner_selection(CornerTypeSelection(CornerTypeId.C03))
    assert (c03.type_id, c03.cross_mode, c03.direction, c03.amount_t) == (
        CornerTypeId.CROSS, CrossCornerMode.EXTRA_CUT, CornerDirection.BOTH, 0.5,
    )

    c04 = normalize_corner_selection(CornerTypeSelection(CornerTypeId.C04))
    assert c04.type_id is CornerTypeId.INSERT_OVERLAY
    assert c04.amount_t == pytest.approx(1.0)
    assert c04.secondary_retain_t == pytest.approx(0.5)
    assert c04.secondary_depth_t == pytest.approx(2.0)


def test_cross_parameters_are_semantic_not_rotation_driven():
    retain_h = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.RETAIN,
        direction=CornerDirection.HEIGHT,
        amount_t=1.5,
    )
    relief = resolve_corner_relief(retain_h, fold_u=20, fold_v=15, thickness=2, fw=25)
    assert relief.primary_u == pytest.approx(20)
    assert relief.primary_v == pytest.approx(12)

    extra_w = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.WIDTH,
        amount_t=0.75,
    )
    relief = resolve_corner_relief(extra_w, fold_u=20, fold_v=15, thickness=2, fw=25)
    assert relief.primary_u == pytest.approx(21.5)
    assert relief.primary_v == pytest.approx(15)


def test_overlay_endcap_structural_blank_uses_finished_width_and_has_no_x_bends():
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.WIDTH,
        amount_t=1.5,
    )
    overlay = CornerTypeSelection(CornerTypeId.OVERLAY)
    policy = FourCornerTypePolicy(
        bottom_left=bottom, bottom_right=bottom,
        top_left=overlay, top_right=overlay, fw=25.0,
    )

    result = build_unknown_endcap_result(
        w=400, d=250, t=2, fw=25,
        yl1=15, yr1=15, ytop1=0, ybottom1=15,
        corner_policy=policy,
        x_topology=resolve_endcap_assembly_semantics(overlay).x_topology,
    )

    assert result.width == pytest.approx(400.0)
    assert result.topology.left_fold == pytest.approx(0.0)
    assert result.topology.right_fold == pytest.approx(0.0)
    assert {bend.name for bend in result.bends}.isdisjoint({"left", "right"})


def test_overlay_is_single_stage_fixed_height_retain():
    relief = resolve_corner_relief(
        CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.25),
        fold_u=15, fold_v=16, thickness=2, fw=25,
    )
    assert relief.primary_u == pytest.approx(40)
    assert relief.primary_v == pytest.approx(38.5)
    assert relief.secondary_u is None
    assert relief.secondary_depth is None


def test_insert_canonicalization_strips_illegal_secondary_parameters():
    selection = CornerTypeSelection(
        CornerTypeId.INSERT,
        amount_t=1.0,
        secondary_retain_t=0.5,
        secondary_depth_t=2.0,
    )
    assert selection.type_id is CornerTypeId.INSERT
    assert selection.secondary_retain_t is None
    assert selection.secondary_depth_t is None


def test_insert_raw_state_cannot_preserve_secondary_parameters():
    from phase6_endcap_semantics import apply_box_assembly_type_to_raw_state

    state = {
        part: {
            "top_left": {
                "type_id": "INSERT", "amount_t": 1.0,
                "secondary_retain_t": 0.5, "secondary_depth_t": 2.0,
            },
            "top_right": {
                "type_id": "INSERT", "amount_t": 1.0,
                "secondary_retain_t": 0.5, "secondary_depth_t": 2.0,
            },
        }
        for part in ("head", "tail")
    }
    pairs = {part: {"top": True, "bottom": True} for part in ("head", "tail")}
    apply_box_assembly_type_to_raw_state(state, pairs, CornerTypeId.INSERT)
    for part in ("head", "tail"):
        for key in ("top_left", "top_right"):
            assert state[part][key]["type_id"] == "INSERT"
            assert "secondary_retain_t" not in state[part][key]
            assert "secondary_depth_t" not in state[part][key]


def test_insert_is_single_stage_and_extra_cuts_height_by_default():
    relief = resolve_corner_relief(
        CornerTypeSelection(CornerTypeId.INSERT, amount_t=1.0),
        fold_u=15, fold_v=16, thickness=2, fw=25,
    )
    assert relief.primary_u == pytest.approx(40)
    assert relief.primary_v == pytest.approx(43)
    assert relief.secondary_u is None
    assert relief.secondary_depth is None


def test_insert_overlay_second_stage_keeps_legacy_c04_cut_coordinate_from_retain_ui():
    relief = resolve_corner_relief(
        CornerTypeSelection(
            CornerTypeId.INSERT_OVERLAY,
            amount_t=1.0,
            secondary_retain_t=0.5,
            secondary_depth_t=2.0,
        ),
        fold_u=15, fold_v=16, thickness=2, fw=25,
    )
    assert relief.primary_u == pytest.approx(40)
    assert relief.primary_v == pytest.approx(39)
    # UI 顯示 0.5T 留肉；實際 C04 二級切線仍是側折 + 0.5T。
    assert relief.secondary_u == pytest.approx(16)
    assert relief.secondary_depth == pytest.approx(4)


def test_fixed_vault_endcap_preserves_legacy_c04_secondary_geometry():
    g = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    dims = calculate_endcap_relief_dimensions(g, ReliefConfig())
    assert dims.top_secondary_left == pytest.approx(16.0)
    assert dims.top_secondary_right == pytest.approx(16.0)
    assert dims.top_secondary_depth_left == pytest.approx(4.0)
    assert dims.top_secondary_depth_right == pytest.approx(4.0)


def test_box_body_height_is_derived_from_head_and_tail_corner_policies():
    overlay = _policy(CornerTypeId.INSERT_OVERLAY)
    insert = _policy(CornerTypeId.INSERT)

    assert _box(head=overlay, tail=overlay).height == pytest.approx(596.0)
    assert _box(head=insert, tail=overlay).height == pytest.approx(598.0)
    assert _box(head=overlay, tail=insert).height == pytest.approx(598.0)
    assert _box(head=insert, tail=insert).height == pytest.approx(600.0)


def test_box_body_default_remains_vault_h_minus_2t():
    assert _box().height == pytest.approx(596.0)


def test_manual_corner_editor_state_uses_new_ids_and_preserves_parameters():
    state = new_manual_corner_state(["head"])["head"]
    assert all(sel.type_id is CornerTypeId.CROSS for sel in state.values())
    assert all(sel.cross_mode is CrossCornerMode.STANDARD for sel in state.values())

    pair_same = {"top": True, "bottom": True}
    selection = CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY,
        amount_t=1.25,
        secondary_retain_t=0.75,
        secondary_depth_t=2.5,
    )
    apply_manual_corner_selection(state, pair_same, "top", selection)
    assert state["top_left"] == selection
    assert state["top_right"] == selection

from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
from ae_engine.sheetmetal_features import box_body_face_contexts_from_strip
import ae_engine.manufacturing_api as manufacturing_api


def test_box_body_face_coordinates_follow_corner_derived_vertical_offsets():
    overlay = _policy(CornerTypeId.INSERT_OVERLAY)
    insert = _policy(CornerTypeId.INSERT)

    overlay_result = _box(head=overlay, tail=overlay)
    overlay_ctx = box_body_face_contexts_from_strip(
        overlay_result.topology, w=400, h=600, d=250, t=2,
        head_corner_policy=overlay, tail_corner_policy=overlay,
    )["back"]
    assert overlay_ctx.local_to_unfolded(type("P", (), {"x": 2.0, "y": 2.0})()).y == pytest.approx(0.0)
    assert overlay_ctx.unfolded_to_local(type("P", (), {"x": overlay_ctx.unfolded_min_x, "y": 596.0})()).y == pytest.approx(598.0)

    insert_result = _box(head=insert, tail=insert)
    insert_ctx = box_body_face_contexts_from_strip(
        insert_result.topology, w=400, h=600, d=250, t=2,
        head_corner_policy=insert, tail_corner_policy=insert,
    )["back"]
    assert insert_ctx.local_to_unfolded(type("P", (), {"x": 2.0, "y": 0.0})()).y == pytest.approx(0.0)
    assert insert_ctx.unfolded_to_local(type("P", (), {"x": insert_ctx.unfolded_min_x, "y": 600.0})()).y == pytest.approx(600.0)


def test_box_body_contract_and_api_pass_head_tail_corner_policies(monkeypatch, tmp_path):
    head = _policy(CornerTypeId.INSERT)
    tail = _policy(CornerTypeId.INSERT_OVERLAY)
    spec = BoxBodyPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        head_corner_policy=head, tail_corner_policy=tail,
    )
    captured = {}

    def fake_export(filepath, **kwargs):
        captured.update(kwargs)
        tmp_path.joinpath("body.dxf").write_text("ok", encoding="utf-8")

    monkeypatch.setattr(manufacturing_api.ae, "export_box_body_dxf", fake_export)
    manufacturing_api._box_body_export(spec, str(tmp_path / "body.dxf"), ManufacturingContext())
    assert captured["head_corner_policy"] is head
    assert captured["tail_corner_policy"] is tail

from ae_engine.corner_type_ui import build_corner_type_preview_geometry
from ae_engine.sheetmetal_geometry import EDITABLE_CORNER_TYPE_IDS


def test_preview_catalog_uses_semantic_types_and_parameterized_real_geometry():
    for type_id in EDITABLE_CORNER_TYPE_IDS:
        preview = build_corner_type_preview_geometry(CornerTypeSelection(type_id))
        assert preview.cut_paths
        assert preview.bend_paths

    one_t = build_corner_type_preview_geometry(
        CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.0)
    )
    two_t = build_corner_type_preview_geometry(
        CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=2.0)
    )
    assert one_t.cut_paths != two_t.cut_paths

import ae_engine.ae as ae
from ae_engine.sheetmetal_drawing import PolylinePrimitive


def test_ae_box_body_scene_uses_corner_policies_for_real_structural_height():
    insert = _policy(CornerTypeId.INSERT)
    scene = ae._build_box_body_scene(
        w=400, h=600, d=250, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=0,
        head_corner_policy=insert, tail_corner_policy=insert,
    )
    cutting = [p for p in scene.primitives if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"]
    assert cutting
    ys = [point.y for primitive in cutting for point in primitive.points]
    assert max(ys) == pytest.approx(600.0)
