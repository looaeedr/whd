# -*- coding: utf-8 -*-
import json
from pathlib import Path

import pytest

from ae_engine.certified_relief_registry import evaluate_relief_formula_record


REGISTRY = Path(__file__).resolve().parents[1] / "基準檔" / "截角資料庫" / "certified_relief_rules.json"
RULE_ID = "RECEIVING_ENDCAP_BOTTOM_WRAP_V1"


def _rule():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return next(row for row in payload["rules"] if row["rule_id"] == RULE_ID)


def _eval(*, t=2.0, side_fold=15.0, rear_bend=15.0, ybottom1=15.0, reserve_u=2.0, reserve_v=1.0):
    rule = _rule()
    return evaluate_relief_formula_record(
        rule,
        {
            "T": t,
            "FW": 29.0,
            "side_fold": side_fold,
            "rear_bend": rear_bend,
            "ybottom1": ybottom1,
            "ytop1": 16.0,
            "mating_width": 0.0,
            "effective_mating_width": 0.0,
            "fold_u": side_fold,
            "fold_v": ybottom1,
            "clearance": 0.0,
            "reserve_u": reserve_u,
            "reserve_v": reserve_v,
        },
    )


def test_receiving_bottom_wrap_rule_is_data_driven_and_names_both_joints():
    rule = _rule()
    assert rule["cabinet_family"] == "受電箱"
    assert rule["joint_face"] == "BOTTOM"
    assert rule["assembly_intent"] == "ANY"
    assert [row["relation"] for row in rule["joint_signature"]] == ["WRAP"]
    assert rule["topology_levels"] == 2
    assert rule["geometry_inputs"] == [
        "ENDCAP_SIDE_FOLD", "BOX_SIDE_REAR_BEND", "ENDCAP_YBOTTOM1", "SHEET_THICKNESS",
        "BOTTOM_RELIEF_RESERVE_U", "BOTTOM_RELIEF_RESERVE_V",
    ]
    assert rule["formula"] == {
        "primary_u": "side_fold + rear_bend - reserve_u",
        "primary_v": "ybottom1 - reserve_v",
        "secondary_u": "side_fold",
        "secondary_depth": "reserve_v",
    }


def test_receiving_bottom_wrap_default_geometry_is_28x14_plus_15x1():
    assert _eval() == {
        "primary_u": pytest.approx(28.0),
        "primary_v": pytest.approx(14.0),
        "secondary_u": pytest.approx(15.0),
        "secondary_depth": pytest.approx(1.0),
    }


@pytest.mark.parametrize(
    "t,side,rear,ybottom,reserve_u,reserve_v,expected",
    [
        # T no longer changes the explicit reserves.
        (1.0, 15.0, 15.0, 15.0, 2.0, 1.0, (28.0, 14.0, 15.0, 1.0)),
        (3.0, 15.0, 15.0, 15.0, 2.0, 1.0, (28.0, 14.0, 15.0, 1.0)),
        (2.0, 10.0, 15.0, 15.0, 2.0, 1.0, (23.0, 14.0, 10.0, 1.0)),
        (2.0, 20.0, 15.0, 15.0, 2.0, 1.0, (33.0, 14.0, 20.0, 1.0)),
        (2.0, 15.0, 10.0, 15.0, 2.0, 1.0, (23.0, 14.0, 15.0, 1.0)),
        (2.0, 15.0, 20.0, 15.0, 2.0, 1.0, (33.0, 14.0, 15.0, 1.0)),
        (2.0, 15.0, 15.0, 10.0, 2.0, 1.0, (28.0, 9.0, 15.0, 1.0)),
        (2.0, 15.0, 15.0, 20.0, 2.0, 1.0, (28.0, 19.0, 15.0, 1.0)),
        (2.0, 15.0, 15.0, 15.0, 3.5, 2.25, (26.5, 12.75, 15.0, 2.25)),
    ],
)
def test_receiving_bottom_wrap_formula_tracks_geometry_and_explicit_reserves(
    t, side, rear, ybottom, reserve_u, reserve_v, expected
):
    got = _eval(
        t=t, side_fold=side, rear_bend=rear, ybottom1=ybottom,
        reserve_u=reserve_u, reserve_v=reserve_v,
    )
    assert got["primary_u"] == pytest.approx(expected[0])
    assert got["primary_v"] == pytest.approx(expected[1])
    assert got["secondary_u"] == pytest.approx(expected[2])
    assert got["secondary_depth"] == pytest.approx(expected[3])


def _receiving_lookup_fixture(part_key):
    from ae_engine import manufacturing_api
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.sheetmetal_geometry import CornerTypeId
    from phase6_fold_profiles import build_endcap_xy_profiles, profile_to_fold_segments
    from phase6_box_body_structure import default_box_body_structure_state

    snap = {
        "model": "受電箱", "assembly_type": "INSERT_OVERLAY",
        "w": 800.0, "h": 600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "zl1": 24.0, "zr1": 0.0,
    }
    profiles = build_endcap_xy_profiles(snap, part_key=part_key)
    policy = receiving.endcap_corner_policy(frame_width=29.0, thickness=2.0, side_rear_bend=15.0)
    spec = EndCapPartSpec(
        width=800, height=600, depth=350, thickness=2, frame_width=29,
        model_name="受電箱", is_tail=(part_key == "tail"),
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=24, box_fold_right=0,
        fold_profile_x=profile_to_fold_segments(profiles["X"]),
        fold_profile_y=profile_to_fold_segments(profiles["Y"]),
        corner_policy=policy, depth_comp_t=2.0,
    )
    render = manufacturing_api.build_part_render_data(spec)
    structure = default_box_body_structure_state()
    structure = receiving.resolve_box_body_structure_state(structure)
    return render, profiles, structure, CornerTypeId


@pytest.mark.parametrize("part_key,expected_names", [
    ("head", {"top_left", "top_right"}),
    ("tail", {"bottom_left", "bottom_right"}),
])
def test_receiving_bottom_registry_lookup_maps_semantic_bottom_to_physical_corners(part_key, expected_names):
    from ae_engine.certified_relief_registry import lookup_certified_endcap_relief

    render, profiles, structure, CornerTypeId = _receiving_lookup_fixture(part_key)
    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId.INSERT_OVERLAY,
        endcap_render_data=render,
        box_body_x_profile=(),
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        sheet_thickness=2.0,
        cabinet_family="受電箱",
        joint_face="BOTTOM",
        joint_signature_relations=("WRAP",),
        box_body_structure_state=structure,
    )
    assert result is not None
    assert result.rule_id == RULE_ID
    assert result.trust_level.value == "CERTIFIED_FROM_3D"
    by_name = {item.corner_name: item.measurement for item in result.corner_reliefs}
    assert set(by_name) == expected_names
    for measurement in by_name.values():
        assert measurement.primary_u == pytest.approx(28.0)
        assert measurement.primary_v == pytest.approx(14.0)
        assert measurement.secondary_u == pytest.approx(15.0)
        assert measurement.secondary_depth == pytest.approx(1.0)


@pytest.mark.parametrize("part_key", ["head", "tail"])
def test_receiving_manufacturing_uses_bottom_wrap_joint_for_registry_geometry(part_key):
    from ae_engine import manufacturing_api
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
    from ae_engine.assembly_geometry import restore_unrelieved_endcap_material
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.assembly_collision import _measure_canonical_corner_cut
    from phase6_fold_profiles import build_endcap_xy_profiles, profile_to_fold_segments
    from phase6_box_body_structure import default_box_body_structure_state

    snap = {
        "model": "受電箱", "assembly_type": "INSERT_OVERLAY",
        "w": 800.0, "h": 600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "zl1": 24.0, "zr1": 0.0,
    }
    profiles = build_endcap_xy_profiles(snap, part_key=part_key)
    structure = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    policy = receiving.endcap_corner_policy(frame_width=29.0, thickness=2.0, side_rear_bend=15.0)
    spec = EndCapPartSpec(
        width=800, height=600, depth=350, thickness=2, frame_width=29,
        model_name="受電箱", is_tail=(part_key == "tail"),
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=24, box_fold_right=0,
        fold_profile_x=profile_to_fold_segments(profiles["X"]),
        fold_profile_y=profile_to_fold_segments(profiles["Y"]),
        corner_policy=policy, depth_comp_t=2.0,
        box_body_structure_state=structure,
        assembly_joints=(AssemblyJoint(
            f"{part_key}:BOTTOM:test", part_key, "box_body",
            "bottom_edge", "bottom_mating_zone", AssemblyJointRelation.WRAP,
            source=AssemblyJointSource.USER_ADDED, edge="BOTTOM",
        ).to_dict(),),
    )
    render = manufacturing_api.build_part_render_data(spec)
    restored = restore_unrelieved_endcap_material(render.material)
    removed = restored.difference(render.material)
    pieces = [removed] if removed.geom_type == "Polygon" else list(removed.geoms)
    physical = ("top_left", "top_right") if part_key == "head" else ("bottom_left", "bottom_right")
    bounds = tuple(map(float, restored.bounds))
    by_corner = {}
    minx, miny, maxx, maxy = bounds
    for corner in physical:
        is_left = corner.endswith("left")
        is_top = corner.startswith("top")
        for piece in pieces:
            bx0, by0, bx1, by1 = map(float, piece.bounds)
            touches_x = abs((bx0 if is_left else bx1) - (minx if is_left else maxx)) < 1e-6
            touches_y = abs((by1 if is_top else by0) - (maxy if is_top else miny)) < 1e-6
            if touches_x and touches_y:
                by_corner[corner] = _measure_canonical_corner_cut(piece, corner, bounds, 0.0)
                break
    assert set(by_corner) == set(physical)
    for measurement in by_corner.values():
        assert measurement.primary_u == pytest.approx(28.0)
        assert measurement.primary_v == pytest.approx(14.0)
        assert measurement.secondary_u == pytest.approx(15.0)
        assert measurement.secondary_depth == pytest.approx(1.0)


@pytest.mark.parametrize(
    "t,left,right,rear,bottom,expected_left,expected_right",
    [
        (2.0, 15.0, 15.0, 15.0, 15.0, (28.0, 14.0, 15.0, 1.0), (28.0, 14.0, 15.0, 1.0)),
        (1.0, 15.0, 20.0, 15.0, 15.0, (29.0, 14.5, 15.0, 0.5), (34.0, 14.5, 20.0, 0.5)),
        (2.5, 10.0, 18.0, 20.0, 12.0, (27.5, 10.75, 10.0, 1.25), (35.5, 10.75, 18.0, 1.25)),
    ],
)
def test_side_back_split_3d_projection_derives_bottom_relief_from_formed_world_faces(
    t, left, right, rear, bottom, expected_left, expected_right
):
    from ae_engine.assembly_geometry import derive_side_back_split_endcap_bottom_relief

    result = derive_side_back_split_endcap_bottom_relief(
        width=800.0, height=600.0, thickness=t,
        side_fold_left=left, side_fold_right=right,
        side_rear_bend=rear, bottom_fold=bottom,
    )
    for side, expected in (("left", expected_left), ("right", expected_right)):
        relief = result[side]["relief"]
        assert (relief.primary_u, relief.primary_v, relief.secondary_u, relief.secondary_depth) == pytest.approx(expected)
        evidence = result[side]["world_evidence"]
        assert evidence["illegal_overlap_u"] == pytest.approx(rear - t)
        assert evidence["illegal_overlap_v"] == pytest.approx(bottom - 0.5 * t)
        assert evidence["wrap_contact_depth"] == pytest.approx(0.5 * t)


def test_receiving_bottom_registry_carries_independent_3d_face_projection_evidence():
    from ae_engine.certified_relief_registry import lookup_certified_endcap_relief
    from ae_engine.sheetmetal_geometry import CornerTypeId

    render, profiles, structure, _ = _receiving_lookup_fixture("head")
    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId.INSERT_OVERLAY,
        endcap_render_data=render,
        box_body_x_profile=(),
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        sheet_thickness=2.0,
        cabinet_family="受電箱",
        joint_face="BOTTOM",
        joint_signature_relations=("WRAP",),
        box_body_structure_state=structure,
    )
    evidence = dict(result.geometry_evidence or {})
    assert evidence["source"] == "SIDE_BACK_SPLIT_3D_FACE_PROJECTION"
    projected = evidence["projection_by_corner"]
    for corner in ("top_left", "top_right"):
        row = projected[corner]
        assert row["illegal_overlap_u"] == pytest.approx(13.0)
        assert row["illegal_overlap_v"] == pytest.approx(14.0)
        assert row["wrap_contact_depth"] == pytest.approx(1.0)


def test_receiving_bottom_reserves_are_explicit_adjustable_mm_not_fixed_t_multiples():
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import default_box_body_structure_state

    state = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    assert receiving.bottom_relief_reserves(state) == pytest.approx((2.0, 1.0))

    changed = receiving.set_bottom_relief_reserves(state, reserve_u=3.5, reserve_v=2.25)
    assert receiving.bottom_relief_reserves(changed) == pytest.approx((3.5, 2.25))


def test_receiving_bottom_formula_uses_adjustable_reserves_instead_of_t():
    rule = _rule()
    assert rule["formula"] == {
        "primary_u": "side_fold + rear_bend - reserve_u",
        "primary_v": "ybottom1 - reserve_v",
        "secondary_u": "side_fold",
        "secondary_depth": "reserve_v",
    }
    got = evaluate_relief_formula_record(
        rule,
        {
            "T": 3.0,
            "FW": 29.0,
            "side_fold": 15.0,
            "rear_bend": 15.0,
            "ybottom1": 15.0,
            "ytop1": 16.0,
            "mating_width": 0.0,
            "effective_mating_width": 0.0,
            "fold_u": 15.0,
            "fold_v": 15.0,
            "clearance": 0.0,
            "reserve_u": 4.0,
            "reserve_v": 2.5,
        },
    )
    assert got == {
        "primary_u": pytest.approx(26.0),
        "primary_v": pytest.approx(12.5),
        "secondary_u": pytest.approx(15.0),
        "secondary_depth": pytest.approx(2.5),
    }


def test_receiving_external_wrap_is_an_explicit_adjustable_structure_option():
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import default_box_body_structure_state

    state = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    assert receiving.bottom_external_wrap_enabled(state) is True
    disabled = receiving.set_bottom_external_wrap(state, False)
    assert receiving.bottom_external_wrap_enabled(disabled) is False
    enabled = receiving.set_bottom_external_wrap(disabled, True)
    assert receiving.bottom_external_wrap_enabled(enabled) is True


def test_receiving_bottom_wrap_can_be_disabled_without_applying_wrap_registry_replacement():
    from ae_engine import manufacturing_api
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import EndCapPartSpec
    from phase6_fold_profiles import build_endcap_xy_profiles, profile_to_fold_segments
    from phase6_box_body_structure import default_box_body_structure_state

    snap = {
        "model": "受電箱", "assembly_type": "INSERT_OVERLAY",
        "w": 800.0, "h": 600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "zl1": 24.0, "zr1": 0.0,
    }
    profiles = build_endcap_xy_profiles(snap, part_key="head")
    structure = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    structure = receiving.set_bottom_external_wrap(structure, False)
    policy = receiving.endcap_corner_policy(frame_width=29.0, thickness=2.0, side_rear_bend=15.0)
    spec = EndCapPartSpec(
        width=800, height=600, depth=350, thickness=2, frame_width=29,
        model_name="受電箱", is_tail=False,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=24, box_fold_right=0,
        fold_profile_x=profile_to_fold_segments(profiles["X"]),
        fold_profile_y=profile_to_fold_segments(profiles["Y"]),
        corner_policy=policy, depth_comp_t=2.0,
        box_body_structure_state=structure,
    )
    render = manufacturing_api.build_part_render_data(spec)
    assert "receiving_bottom_relief_rule" not in dict(render.metadata or {})

@pytest.mark.parametrize("intent_name", ["INSERT", "OVERLAY", "INSERT_OVERLAY"])
def test_receiving_bottom_wrap_registry_is_independent_from_endcap_assembly_intent(intent_name):
    from ae_engine.certified_relief_registry import lookup_certified_endcap_relief
    from ae_engine.sheetmetal_geometry import CornerTypeId

    render, profiles, structure, _ = _receiving_lookup_fixture("head")
    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId(intent_name),
        endcap_render_data=render,
        box_body_x_profile=(),
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        sheet_thickness=2.0,
        cabinet_family="受電箱",
        joint_face="BOTTOM",
        joint_signature_relations=("WRAP",),
        box_body_structure_state=structure,
    )
    assert result is not None
    assert result.rule_id == RULE_ID
    assert result.rule.assembly_intent is None


def test_receiving_bottom_wrap_adjustable_reserve_does_not_require_recertifying_3d_baseline():
    from ae_engine.certified_relief_registry import lookup_certified_endcap_relief
    from ae_engine.cabinet_types import receiving
    from ae_engine.sheetmetal_geometry import CornerTypeId

    render, profiles, structure, _ = _receiving_lookup_fixture("head")
    structure = receiving.set_bottom_relief_reserves(structure, reserve_u=3.5, reserve_v=2.25)
    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId.OVERLAY,
        endcap_render_data=render,
        box_body_x_profile=(),
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        sheet_thickness=2.0,
        cabinet_family="受電箱",
        joint_face="BOTTOM",
        joint_signature_relations=("WRAP",),
        box_body_structure_state=structure,
    )
    assert result is not None
    for item in result.corner_reliefs:
        assert item.measurement.primary_u == pytest.approx(26.5)
        assert item.measurement.primary_v == pytest.approx(12.75)
        assert item.measurement.secondary_u == pytest.approx(15.0)
        assert item.measurement.secondary_depth == pytest.approx(2.25)
    # 3D evidence is still the certified physical baseline, not a second formula owner.
    evidence = dict(result.geometry_evidence or {})
    assert evidence["projection_by_corner"]
