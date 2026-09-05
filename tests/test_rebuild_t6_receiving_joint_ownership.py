# -*- coding: utf-8 -*-
from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource


def _bottom_joint(part, relation):
    return AssemblyJoint(
        f"{part}:BOTTOM:test", part, "box_body", "bottom_edge", "bottom_mating_zone",
        relation, source=AssemblyJointSource.USER_ADDED, edge="BOTTOM",
    ).to_dict()


def _receiving_spec(*, relation, legacy_enabled, part="head"):
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import EndCapPartSpec
    from phase6_box_body_structure import default_box_body_structure_state
    from phase6_fold_profiles import build_endcap_xy_profiles, profile_to_fold_segments

    snapshot = {
        "model": "受電箱", "assembly_type": "INSERT_OVERLAY",
        "w": 800.0, "h": 600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "zl1": 24.0, "zr1": 0.0,
    }
    profiles = build_endcap_xy_profiles(snapshot, part_key=part)
    structure = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    structure = receiving.set_bottom_external_wrap(structure, legacy_enabled)
    policy = receiving.endcap_corner_policy(frame_width=29.0, thickness=2.0, side_rear_bend=15.0)
    return EndCapPartSpec(
        width=800, height=600, depth=350, thickness=2, frame_width=29,
        model_name="受電箱", is_tail=(part == "tail"),
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=24, box_fold_right=0,
        fold_profile_x=profile_to_fold_segments(profiles["X"]),
        fold_profile_y=profile_to_fold_segments(profiles["Y"]),
        corner_policy=policy, depth_comp_t=2.0,
        box_body_structure_state=structure,
        assembly_joints=(_bottom_joint(part, relation),),
    )


def test_receiving_bottom_insert_stays_standard_even_if_legacy_wrap_flag_is_true():
    from ae_engine import manufacturing_api
    spec = _receiving_spec(relation=AssemblyJointRelation.INSERT, legacy_enabled=True)
    render = manufacturing_api.build_part_render_data(spec)
    assert "receiving_bottom_relief_rule" not in dict(render.metadata or {})


def test_receiving_bottom_wrap_hits_registry_even_if_legacy_wrap_flag_is_false_and_preserves_topology():
    from ae_engine import manufacturing_api
    spec = _receiving_spec(relation=AssemblyJointRelation.WRAP, legacy_enabled=False)
    render = manufacturing_api.build_part_render_data(spec)
    trace = dict(render.metadata or {}).get("receiving_bottom_relief_rule")
    assert trace and trace["rule_id"] == "RECEIVING_ENDCAP_BOTTOM_WRAP_V1"
    assert render.unfolded_topology is not None

def test_wrap_overlay_bottom_is_fixed_wrap_and_editor_rejects_insert():
    import pytest
    from ae_engine.assembly_joint import (
        edge_relation_for_part,
        set_part_edge_relation,
        migrate_legacy_snapshot_joints,
    )
    snap = migrate_legacy_snapshot_joints({
        "model": "受電箱", "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    })
    with pytest.raises(ValueError, match="not allowed"):
        set_part_edge_relation(snap, "head", "BOTTOM", AssemblyJointRelation.INSERT)
    assert edge_relation_for_part(snap, "head", "BOTTOM") is AssemblyJointRelation.WRAP
    assert edge_relation_for_part(snap, "tail", "BOTTOM") is AssemblyJointRelation.WRAP

def test_bottom_wrap_ui_projection_uses_fixed_wrap_graph_over_legacy_mirror():
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints, set_part_edge_relation
    from phase6_endcap_semantics import normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap
    snap = migrate_legacy_snapshot_joints({
        "model": "受電箱", "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    })
    state = normalize_endcap_bottom_wrap_state({"model": "受電箱"})  # compatibility mirror only
    assert resolve_endcap_bottom_wrap(snap, "head", state=state)["enabled"] is True
    assert resolve_endcap_bottom_wrap(snap, "tail", state=state)["enabled"] is True

def test_legacy_explicit_bottom_wrap_migrates_once_but_absent_field_does_not_invent_wrap():
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints, edge_relation_for_part
    explicit = migrate_legacy_snapshot_joints({
        "model": "受電箱", "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
        "endcap_bottom_wrap": {
            "mode": "INDEPENDENT",
            "head": {"enabled": True, "reserve_u": 2.0, "reserve_v": 1.0},
            "tail": {"enabled": False, "reserve_u": 2.0, "reserve_v": 1.0},
        },
    })
    assert edge_relation_for_part(explicit, "head", "BOTTOM") is AssemblyJointRelation.WRAP
    assert edge_relation_for_part(explicit, "tail", "BOTTOM") is AssemblyJointRelation.INSERT

    absent = migrate_legacy_snapshot_joints({
        "model": "受電箱", "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    })
    assert edge_relation_for_part(absent, "head", "BOTTOM") is AssemblyJointRelation.INSERT
    assert edge_relation_for_part(absent, "tail", "BOTTOM") is AssemblyJointRelation.INSERT

def test_receiving_known_endcap_bottom_projection_is_standard_not_legacy_insert_overlay():
    from ae_engine.corner_type_ui import known_model_corner_state
    from ae_engine.cabinet_types.receiving import endcap_corner_policy
    from ae_engine.sheetmetal_geometry import CornerTypeId, CrossCornerMode

    state = known_model_corner_state(("head", "tail"), cabinet_family="受電箱")
    for part in ("head", "tail"):
        for corner in ("bottom_left", "bottom_right"):
            sel = state[part][corner]
            assert sel.type_id is CornerTypeId.CROSS
            assert sel.cross_mode is CrossCornerMode.STANDARD

    policy = endcap_corner_policy(frame_width=29.0, thickness=2.0, side_rear_bend=15.0)
    assert policy.bottom_left.type_id is CornerTypeId.CROSS
    assert policy.bottom_left.cross_mode is CrossCornerMode.STANDARD
