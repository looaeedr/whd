from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import Polygon

from ae_engine.ae import get_box_body_baseline_face_features
from ae_engine.ae_calculations import calculate_y_depth, calculate_z_length
from ae_engine.assembly_collision import _render_data_rebuilt_from_material
from ae_engine.assembly_collision_basic import (
    _scene_with_replaced_primary_cutting,
    apply_endcap_relief_candidate,
)
from ae_engine.assembly_mesh_reuse import mesh_build_scope, reuse_local_mesh
from ae_engine.baseline_source import baseline_cutting_bounds
from ae_engine.certified_relief_registry import (
    CertifiedReliefRegistryError,
    build_runtime_relief_rules_from_external,
    evaluate_editable_endcap_rule_record,
    lookup_certified_endcap_relief,
    lookup_certified_endcap_relief_from_graph,
)
from ae_engine.manufacturing_render_data import (
    FoldGuide,
    PartRenderData,
)
from ae_engine.sheetmetal_drawing import (
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
)
from ae_engine.sheetmetal_features import (
    FeaturePlacement,
    ProfileFeature,
    Vec2,
    resolve_features_in_finished_face,
)
from phase6_fold_profiles import (
    build_box_body_profile,
    build_endcap_xy_profiles,
    build_linked_endcap_xy_profiles,
    read_box_body_profile,
)


def _rect_render_data(w: float = 200.0, d: float = 150.0) -> PartRenderData:
    poly = Polygon([(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)])
    cutting = PolylinePrimitive(
        points=(
            Vec2(0.0, 0.0),
            Vec2(w, 0.0),
            Vec2(w, d),
            Vec2(0.0, d),
        ),
        layer="CUTTING",
        closed=True,
    )
    bend = LinePrimitive(
        p1=Vec2(0.0, 20.0),
        p2=Vec2(w, 20.0),
        layer="BEND",
    )
    scene = DrawingScene(primitives=[cutting, bend])
    return PartRenderData(
        scene=scene,
        material=poly,
        fold_guides=(FoldGuide("y", 20.0, 0.0, w),),
    )


def _standard_profiles():
    body_x = (
        {"length": 16.0, "angle": 90.0, "phase6_key": "zl2"},
        {"length": 18.0, "angle": 90.0, "phase6_key": "zl1"},
        {"length": 25.0, "angle": 90.0, "phase6_key": "fw_left"},
        {"length": 150.0, "angle": 90.0, "phase6_key": "box_d"},
        {"length": 500.0, "angle": 0.0, " core": True, "phase6_key": "box_w"},
        {"length": 150.0, "angle": -90.0, "phase6_key": "box_d_right"},
        {"length": 25.0, "angle": -90.0, "phase6_key": "fw_right"},
        {"length": 18.0, "angle": -90.0, "phase6_key": "zr1"},
        {"length": 16.0, "angle": -90.0, "phase6_key": "zr2"},
    )
    end_x = (
        {"length": 18.0, "angle": -90.0, "phase6_key": "yl1"},
        {"length": 200.0, "angle": 0.0, "core": True, "phase6_key": "endcap_w_core"},
        {"length": 18.0, "angle": -90.0, "phase6_key": "yr1"},
    )
    end_y = (
        {"length": 20.0, "angle": -90.0, "phase6_key": "ytop1"},
        {"length": 150.0, "angle": 0.0, "core": True, "phase6_key": "endcap_d_core"},
        {"length": 25.0, "angle": -90.0, "phase6_key": "fw"},
        {"length": 18.0, "angle": -90.0, "phase6_key": "ybottom1"},
    )
    return body_x, end_x, end_y


# --- D1-01: Receiving EndCap FW double-compensation & single-side FW read ---
def test_d1_01_receiving_linked_endcap_fw_no_double_compensation():
    snapshot = {
        "model": "受電箱",
        "cabinet_type": "受電箱",
        "w": 600.0,
        "h": 800.0,
        "d": 250.0,
        "t": 2.0,
        "fw": 25.0,
        "yl1": 18.0,
        "yr1": 18.0,
        "ytop1": 20.0,
        "ybottom1": 18.0,
    }
    box_profile = build_box_body_profile(snapshot)
    direct = build_endcap_xy_profiles(snapshot, part_key="head")
    linked = build_linked_endcap_xy_profiles(snapshot, box_profile)
    direct_fw_seg = next(s for s in direct["Y"] if s.get("phase6_key") == "fw")
    linked_fw_seg = next(s for s in linked["head"]["Y"] if s.get("phase6_key") == "fw")
    assert linked_fw_seg["len"] == pytest.approx(direct_fw_seg["len"])
    assert linked_fw_seg.get("ui_len_add") == pytest.approx(direct_fw_seg.get("ui_len_add"))


def test_d1_01_read_box_body_profile_single_side_fw_uses_ui_len():
    snapshot = {
        "model": "受電箱",
        "cabinet_type": "受電箱",
        "w": 600.0,
        "h": 800.0,
        "d": 250.0,
        "t": 2.0,
        "fw": 25.0,
    }
    single_side_x = [
        {"len": 21.0, "formed_length": 25.0, "ui_len_add": 4.0, "angle": 90.0, "phase6_key": "fw_left"},
        {"len": 246.0, "formed_length": 250.0, "ui_len_add": 4.0, "angle": 90.0, "core": "D", "phase6_key": "box_d"},
        {"len": 596.0, "formed_length": 600.0, "ui_len_add": 4.0, "angle": 0.0, "core": "W", "phase6_key": "box_w"},
        {"len": 246.0, "formed_length": 250.0, "ui_len_add": 4.0, "angle": -90.0, "core": "D", "phase6_key": "box_d_right"},
    ]
    parsed = read_box_body_profile(single_side_x, snapshot)
    assert parsed["fw"] == 25


# --- D1-02: build_runtime_relief_rules_from_external preserves special evaluators for rev 1 ---
def test_d1_02_build_runtime_relief_rules_from_external_preserves_special_evaluators():
    rules = {rule.rule_id: rule for rule in build_runtime_relief_rules_from_external()}
    from ae_engine.certified_relief_registry import _SPECIAL_RULE_EVALUATORS

    for rule_id, expected_eval in _SPECIAL_RULE_EVALUATORS.items():
        if rule_id in rules and int(rules[rule_id].revision) == 1:
            assert rules[rule_id].evaluator is expected_eval


# --- D1-03: evaluate_editable_endcap_rule_record forwards box_body_structure_state ---
def test_d1_03_evaluate_editable_endcap_rule_record_forwards_box_structure_state():
    render_data = _rect_render_data(200.0, 150.0)
    body_x, end_x, end_y = _standard_profiles()
    record = {
        "rule_id": "CANDIDATE_STRUCT_TEST",
        "assembly_intent": "INSERT",
        "joint_face": "TOP",
        "topology_levels": 1,
        "joint_signature": [{"relation": "INSERT"}],
        "formula": {
            "primary_u": "rear_bend + clearance",
            "primary_v": "FW",
        },
        "source": "unit-test",
    }
    structure_state = {
        "active_type": "three_piece_side_back_split",
        "configs": {
            "three_piece_side_back_split": {
                "side_rear_bend": 33.0,
            }
        },
    }
    res = evaluate_editable_endcap_rule_record(
        record,
        endcap_render_data=render_data,
        box_body_x_profile=body_x,
        endcap_x_profile=end_x,
        endcap_y_profile=end_y,
        sheet_thickness=2.0,
        box_body_structure_state=structure_state,
    )
    assert res is not None
    assert res.corner_reliefs[0].measurement.primary_u == pytest.approx(33.0)


# --- D1-04: _end_cap_export uses save_part_render_data_dxf ---
def test_d1_04_end_cap_export_uses_save_part_render_data_dxf(tmp_path: Path):
    from ae_engine import manufacturing_api
    from ae_engine.contracts import EndCapPartSpec, ManufacturingContext

    fake_render_data = _rect_render_data()
    out_file = tmp_path / "endcap_test.dxf"
    spec = EndCapPartSpec(
        model_name="1200x700x280",
        width=700.0,
        height=1200.0,
        depth=280.0,
        thickness=2.0,
        frame_width=25.0,
        fold_left=18.0,
        fold_right=18.0,
        fold_top=20.0,
        fold_bottom=18.0,
        box_fold_left=18.0,
        box_fold_right=18.0,
        fold_profile_x=({"len": 18.0, "angle": 90.0, "phase6_key": "yl1"},),
    )
    ctx = ManufacturingContext()
    with (
        patch.object(manufacturing_api, "resolve_endcap_request", return_value=None),
        patch.object(manufacturing_api, "build_part_render_data", return_value=fake_render_data),
        patch.object(manufacturing_api, "save_part_render_data_dxf", return_value=out_file) as mock_save_part,
    ):
        manufacturing_api._end_cap_export(spec, str(out_file), ctx)
        mock_save_part.assert_called_once_with(fake_render_data, str(out_file), overwrite=True)


# --- D1-05: _scene_with_replaced_primary_cutting preserves interior holes, clips BEND, updates fold_guides ---
def test_d1_05_scene_replacement_clips_bend_preserves_holes_and_updates_fold_guides():
    rd = _rect_render_data(200.0, 150.0)
    # Material with corner cut at y=20 (clipping bend from x=0..200 to x=30..170) and an interior hole
    notched_shell = [(0.0, 30.0), (30.0, 30.0), (30.0, 0.0), (170.0, 0.0), (170.0, 30.0), (200.0, 30.0), (200.0, 150.0), (0.0, 150.0)]
    hole = [(80.0, 60.0), (120.0, 60.0), (120.0, 90.0), (80.0, 90.0)]
    new_material = Polygon(notched_shell, [hole])

    updated_scene = _scene_with_replaced_primary_cutting(rd.scene, new_material)
    cutting_polys = [
        p for p in updated_scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING" and p.closed
    ]
    # Primary exterior + 1 interior hole polyline
    assert len(cutting_polys) == 2

    bends = [
        p for p in updated_scene.primitives
        if isinstance(p, LinePrimitive) and p.layer == "BEND"
    ]
    assert len(bends) == 1
    assert min(bends[0].p1.x, bends[0].p2.x) == pytest.approx(30.0)
    assert max(bends[0].p1.x, bends[0].p2.x) == pytest.approx(170.0)

    rebuilt = _render_data_rebuilt_from_material(rd, new_material)
    assert len(rebuilt.fold_guides) == 1
    guide = rebuilt.fold_guides[0]
    assert guide.span_start == pytest.approx(30.0)
    assert guide.span_end == pytest.approx(170.0)


# --- D1-06: reuse_local_mesh distinguishes formed_length and phase6_key ---
def test_d1_06_mesh_cache_key_includes_formed_length_and_phase6_key():
    poly = Polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 80.0), (0.0, 80.0)])
    x1 = ({"len": 21.0, "formed_length": 25.0, "angle": 90.0, "phase6_key": "fw_left"},)
    x2 = ({"len": 21.0, "formed_length": 23.0, "angle": 90.0, "phase6_key": "fw_left"},)
    x3 = ({"len": 21.0, "formed_length": 25.0, "angle": 90.0, "phase6_key": "zl1"},)
    y = ({"len": 80.0, "angle": 0.0, "core": True},)

    calls = []

    @reuse_local_mesh
    def _dummy_build(material, x_profile, y_profile, *, fold_exemptions=(), fold_guides=()):
        calls.append((x_profile, y_profile))
        return object()

    with mesh_build_scope():
        r1 = _dummy_build(poly, x1, y)
        r2 = _dummy_build(poly, x2, y)
        r3 = _dummy_build(poly, x3, y)
        assert r1 is not r2
        assert r1 is not r3
        assert len(calls) == 3


# --- D1-07: 2-stage formula with secondary_depth == 0.0 does not raise topology mismatch ---
def test_d1_07_two_stage_formula_zero_secondary_depth_succeeds():
    render_data = _rect_render_data(200.0, 150.0)
    body_x, end_x, end_y = _standard_profiles()
    record = {
        "rule_id": "RECEIVING_ENDCAP_BOTTOM_WRAP_ZERO_SEC",
        "assembly_intent": "ANY",
        "joint_face": "BOTTOM",
        "topology_levels": 2,
        "joint_signature": [{"relation": "WRAP"}],
        "geometry_inputs": [
            "BOTTOM_RELIEF_RESERVE_U",
            "BOTTOM_RELIEF_RESERVE_V",
        ],
        "formula": {
            "primary_u": "side_fold",
            "primary_v": "ybottom1",
            "secondary_u": "side_fold + T",
            "secondary_depth": "0",
        },
        "source": "unit-test",
    }
    structure_state = {
        "active_type": "three_piece_side_back_split",
        "configs": {
            "three_piece_side_back_split": {
                "side_rear_bend": 15.0,
                "bottom_relief_reserve_u": 2.0,
                "bottom_relief_reserve_v": 0.0,
            }
        },
    }
    res = evaluate_editable_endcap_rule_record(
        record,
        endcap_render_data=render_data,
        box_body_x_profile=body_x,
        endcap_x_profile=end_x,
        endcap_y_profile=end_y,
        sheet_thickness=2.0,
        box_body_structure_state=structure_state,
    )
    assert res is not None
    assert res.corner_reliefs[0].measurement.secondary_depth == pytest.approx(0.0)


# --- D1-08: lookup_certified_endcap_relief preserves rule.joint_face & graph supports asymmetric L/R ---
def test_d1_08_lookup_certified_endcap_relief_preserves_canonical_joint_face():
    render_data = _rect_render_data(200.0, 150.0)
    body_x, end_x, end_y = _standard_profiles()
    res = lookup_certified_endcap_relief(
        assembly_intent="INSERT",
        joint_face="TOP_LEFT",
        endcap_render_data=render_data,
        box_body_x_profile=body_x,
        endcap_x_profile=end_x,
        endcap_y_profile=end_y,
        sheet_thickness=2.0,
    )
    assert res is not None
    assert res.rule.joint_face == "TOP"


def test_d1_08_lookup_certified_endcap_relief_from_graph_supports_asymmetric_left_right():
    from ae_engine.assembly_joint import (
        AssemblyJoint,
        AssemblyJointRelation,
        ResolvedAssemblyGraph,
    )

    render_data = _rect_render_data(200.0, 150.0)
    body_x, end_x, end_y = _standard_profiles()
    j_top_left = AssemblyJoint(
        joint_id="j_top_left",
        subject_part="head",
        target_part="box_body",
        subject_region="top_left_corner",
        target_region="top_mating_zone",
        relation=AssemblyJointRelation.INSERT,
        edge="TOP",
    )
    j_left = AssemblyJoint(
        joint_id="j_left",
        subject_part="head",
        target_part="box_body",
        subject_region="left_side",
        target_region="left_mating_zone",
        relation=AssemblyJointRelation.INSERT,
        edge="LEFT",
    )
    j_top_right = AssemblyJoint(
        joint_id="j_top_right",
        subject_part="head",
        target_part="box_body",
        subject_region="top_right_corner",
        target_region="top_mating_zone",
        relation=AssemblyJointRelation.OVERLAY,
        edge="TOP",
    )
    j_right = AssemblyJoint(
        joint_id="j_right",
        subject_part="head",
        target_part="box_body",
        subject_region="right_side",
        target_region="right_mating_zone",
        relation=AssemblyJointRelation.INSERT,
        edge="RIGHT",
    )
    graph = ResolvedAssemblyGraph(
        parts=("box_body", "head"),
        joints=(j_top_left, j_left, j_top_right, j_right),
    )
    res = lookup_certified_endcap_relief_from_graph(
        graph=graph,
        endcap_part="head",
        endcap_render_data=render_data,
        box_body_x_profile=body_x,
        endcap_x_profile=end_x,
        endcap_y_profile=end_y,
        sheet_thickness=2.0,
    )
    assert res is not None
    assert "+" in res.rule_id


# --- D1-09 & D1-10: layered_profiles transformed into local and finished-face coordinates ---
def test_d1_09_and_d1_10_layered_profiles_transformed():
    from ae_engine import ae
    from ae_engine.sheetmetal_features import FeatureAnchor, ResolvedProfile

    unfolded_profile = ResolvedProfile(
        points=(Vec2(500.0, 100.0), Vec2(520.0, 120.0)),
        layer="CUTTING",
        source_type="baseline",
        layered_profiles=(
            ("CUTTING", (Vec2(500.0, 100.0), Vec2(520.0, 120.0)), True),
            ("MARKING", (Vec2(505.0, 105.0), Vec2(515.0, 115.0)), False),
        ),
    )
    with patch.object(ae, "get_box_body_baseline_unfolded_features", return_value=[unfolded_profile]):
        face_features = get_box_body_baseline_face_features(
            "1200x700x280",
            zl1=18.0,
            zl2=16.0,
            zr1=18.0,
            zr2=16.0,
            z_comp=0.0,
            w=700.0,
            h=1200.0,
            d=280.0,
            t=2.0,
            fw=25.0,
        )
    assert len(face_features["back"]) == 1
    back_prof = face_features["back"][0]
    assert len(back_prof.layered_profiles) == 2
    assert back_prof.layered_profiles[0][2] is True
    assert back_prof.layered_profiles[1][0] == "MARKING"

    pf = ProfileFeature(
        points=(Vec2(10.0, 20.0), Vec2(30.0, 40.0)),
        anchor=FeatureAnchor.BOTTOM_LEFT,
        offset=Vec2(100.0, 200.0),
        layer="CUTTING",
        layered_profiles=(
            ("CUTTING", (Vec2(10.0, 20.0), Vec2(30.0, 40.0)), True),
            ("BEND", (Vec2(15.0, 25.0), Vec2(25.0, 35.0)), False),
        ),
    )
    resolved = resolve_features_in_finished_face(
        width=500.0,
        height=600.0,
        features=[pf],
    )
    assert len(resolved) == 1
    rp = resolved[0]
    assert len(rp.layered_profiles) == 2
    assert rp.layered_profiles[0][1][0] == Vec2(110.0, 220.0)
    assert rp.layered_profiles[1][1][0] == Vec2(115.0, 225.0)


# --- D1-11: baseline_cutting_bounds filters baseline entities and computes exact ARC bounds ---
def test_d1_11_baseline_cutting_bounds_arc_and_entity_filtering():
    arc_ent = MagicMock()
    arc_ent.dxftype.return_value = "ARC"
    arc_ent.dxf.layer = "CUTTING"
    arc_ent.dxf.center = MagicMock(x=0.0, y=0.0)
    arc_ent.dxf.radius = 100.0
    arc_ent.dxf.start_angle = 30.0
    arc_ent.dxf.end_angle = 60.0

    bounds = baseline_cutting_bounds([arc_ent])
    assert bounds is not None
    min_x, min_y, max_x, max_y = bounds
    assert min_x == pytest.approx(50.0, abs=1e-3)
    assert max_x == pytest.approx(86.60254, abs=1e-3)
    assert min_y == pytest.approx(50.0, abs=1e-3)
    assert max_y == pytest.approx(86.60254, abs=1e-3)


# --- D1-12: calculate_z_length and calculate_y_depth use abs() for negative segment lengths ---
def test_d1_12_calculate_z_length_and_y_depth_negative_inputs():
    z_pos = calculate_z_length(zl1=18.0, zl2=16.0, zr1=18.0, zr2=16.0, FW_val=25.0, W_val=500.0, D_val=200.0, T_val=2.0)
    z_neg = calculate_z_length(zl1=-18.0, zl2=-16.0, zr1=-18.0, zr2=-16.0, FW_val=-25.0, W_val=500.0, D_val=200.0, T_val=2.0)
    assert z_neg == pytest.approx(z_pos)

    y_pos = calculate_y_depth(ytop1=20.0, ybottom1=18.0, D_val=200.0, T_val=2.0, FW_val=25.0)
    y_neg = calculate_y_depth(ytop1=-20.0, ybottom1=-18.0, D_val=200.0, T_val=2.0, FW_val=-25.0)
    assert y_neg == pytest.approx(y_pos)


@pytest.mark.parametrize("intent", ("INSERT", "INSERT_OVERLAY", "OVERLAY"))
def test_d1_certified_default_graph_resolves_both_top_corners(intent):
    """Do not silently replace certified Head/Tail relief with provisional 3D."""
    from ae_engine.assembly_joint import (
        apply_preset_defaults, resolve_actual_graph, _joint_region_matches_corner,
    )
    from ae_engine.corner_resolver import registry_intent_for_corner
    from ae_engine.sheetmetal_geometry import CornerTypeId

    assert _joint_region_matches_corner("top_edge", "top_left")
    assert _joint_region_matches_corner("top_mating_zone", "top_right")
    assert not _joint_region_matches_corner("top_edge", "bottom_left")
    assert not _joint_region_matches_corner("bottom_mating_zone", "top_right")
    assert not _joint_region_matches_corner("top_left", "top_right")

    parts = ("box_body", "head", "tail")
    graph = resolve_actual_graph(parts, apply_preset_defaults(intent, parts=parts))
    for endcap in ("head", "tail"):
        for corner in ("top_left", "top_right"):
            assert registry_intent_for_corner(graph, endcap, corner) is CornerTypeId(intent)
