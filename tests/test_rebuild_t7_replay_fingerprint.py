# -*- coding: utf-8 -*-
from ae_engine.sheetmetal_geometry import CornerTypeId
from ae_engine.assembly_joint import (
    AssemblyJoint, AssemblyJointRelation, AssemblyJointSource, ResolvedAssemblyGraph,
)


def _graph(*, source=AssemblyJointSource.LEGACY_MIGRATED, relation=AssemblyJointRelation.INSERT, region="left_side", jid="a", revision=1):
    return ResolvedAssemblyGraph(("box_body", "head", "tail"), (
        AssemblyJoint(jid, "head", "box_body", region, "left_mating_zone", relation,
                      source=source, edge="LEFT", revision=revision,
                      migration_origin="X" if source is AssemblyJointSource.LEGACY_MIGRATED else "Y"),
    ))


def test_joint_graph_fingerprint_uses_mechanical_semantics_not_provenance_or_legacy_region_alias():
    from ae_engine.assembly_joint import resolved_joint_graph_fingerprint
    legacy = _graph(source=AssemblyJointSource.LEGACY_MIGRATED, region="left_side", jid="legacy", revision=1)
    intent = _graph(source=AssemblyJointSource.INTENT_DERIVED, region="left_edge", jid="intent", revision=99)
    changed = _graph(source=AssemblyJointSource.INTENT_DERIVED, relation=AssemblyJointRelation.OVERLAY, region="left_edge", jid="intent", revision=99)
    assert resolved_joint_graph_fingerprint(legacy) == resolved_joint_graph_fingerprint(intent)
    assert resolved_joint_graph_fingerprint(legacy) != resolved_joint_graph_fingerprint(changed)


def _source(graph_fp, structure_fp="S1", assembly_type="INSERT"):
    return {
        "relief_contract_version": 3,
        "assembly_type": assembly_type,
        "box_body_formed_fw": {"left": 29.0, "right": 29.0},
        "joint_graph_fingerprint": graph_fp,
        "family_structure_fingerprint": structure_fp,
        "cabinet_family": "受電箱",
        "part_profiles": {},
    }


def test_relief_source_match_uses_graph_and_family_structure_not_assembly_mirror():
    import fold_designer_bridge as bridge
    saved = _source("G1", assembly_type="INSERT")
    same_mechanics_different_mirror = _source("G1", assembly_type="OVERLAY")
    graph_changed = _source("G2", assembly_type="INSERT")
    structure_changed = _source("G1", structure_fp="S2", assembly_type="INSERT")
    assert bridge._phase6_relief_source_matches_current(saved, same_mechanics_different_mirror, []) is True
    assert bridge._phase6_relief_source_matches_current(saved, graph_changed, []) is False
    assert bridge._phase6_relief_source_matches_current(saved, structure_changed, []) is False

def test_main_gui_replay_uses_graph_fingerprint_not_legacy_assembly_mirror():
    from types import SimpleNamespace
    import hashlib, json
    import gui
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints, resolved_joint_graph_fingerprint

    joint_state = migrate_legacy_snapshot_joints({
        "assembly_type": "INSERT", "existing_parts": ["box_body", "head", "tail"]
    })
    graph_fp = resolved_joint_graph_fingerprint(joint_state)
    structure = {}
    structure_fp = hashlib.sha256(json.dumps(structure, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    source = {
        "relief_contract_version": 3,
        "assembly_type": "OVERLAY",  # deliberately stale mirror
        "joint_graph_fingerprint": graph_fp,
        "family_structure_fingerprint": structure_fp,
        "cabinet_family": "金庫型",
        "registry_rules": {"head": {"rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", "revision": 1}},
        "part_profiles": {},
    }
    state = {
        "enabled": True, "source": source,
        "parts": {"head": {
            "verified": True, "trust_level": "CERTIFIED",
            "rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", "rule_revision": 1,
            "cuts": [[(0, 0), (2, 0), (2, 2), (0, 2)]],
        }},
    }
    dummy = SimpleNamespace(
        assembly_relief_state=state,
        assembly_joint_state=joint_state,
        workspace_controller=SimpleNamespace(box_body_structure_state=lambda: {}, box_body_profile=lambda: ()),
        _current_box_assembly_type=lambda: CornerTypeId.OVERLAY,
        _baseline_source_model=lambda: "金庫型",
        _phase6_relief_profile_signature=gui.BoxCalculatorGUI._phase6_relief_profile_signature,
    )
    val = {name: 0.0 for name in ("w","h","d","t","fw","zl1","zr1","yl1","yr1","ytop1","ybottom1")}
    cuts = gui.BoxCalculatorGUI._resolved_committed_assembly_relief_cuts(dummy, "head", val, {})
    assert len(cuts) == 1

    dummy.assembly_joint_state = migrate_legacy_snapshot_joints({
        "assembly_type": "OVERLAY", "existing_parts": ["box_body", "head", "tail"]
    })
    assert gui.BoxCalculatorGUI._resolved_committed_assembly_relief_cuts(dummy, "head", val, {}) == ()

def test_relief_source_match_rejects_stale_certified_rule_revision():
    import fold_designer_bridge as bridge
    valid = _source("G1")
    valid["registry_rules"] = {"head": {"rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", "revision": 1}}
    stale = dict(valid)
    stale["registry_rules"] = {"head": {"rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", "revision": 999}}
    assert bridge._phase6_relief_source_matches_current(valid, valid, ["head"]) is True
    assert bridge._phase6_relief_source_matches_current(stale, stale, ["head"]) is False
