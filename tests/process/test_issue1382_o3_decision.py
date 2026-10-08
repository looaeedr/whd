"""DM8-C0 O3 decision: one scene mutation owner, without changing production geometry."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / ".agents/contracts/WHD_DM8_SCENE_MUTATION_OWNER_DECISION_V1.json"


def _decision():
    return json.loads(DECISION.read_text(encoding="utf-8"))


def test_single_explicit_accepted_decision():
    d = _decision()
    assert d["schema"] == "WHD_DM8_SCENE_MUTATION_OWNER_DECISION_V1"
    assert d["status"] == "CURRENT_DESIGN_DECISION"
    assert d["issue"] == 1382
    assert d["decision"] == "DOMAIN_NEUTRAL_MANUFACTURING_SCENE_ACCESS"
    assert d["decision_rationale"]
    assert d["rejected_alternatives"]["ASSEMBLY_MARKING_GEOMETRY_SCENE_OWNER"]
    assert d["no_production_behavior_or_geometry_mutation"] is True


def test_public_seam_has_two_callers_and_no_policy_or_second_oracle():
    d = _decision()
    assert d["scene_access_owner"] == "ae_engine/manufacturing_scene_access.py"
    assert set(d["required_production_callers"]) == {
        "ae_engine/receiving_joint_marking.py",
        "ae_engine/receiving_pairing_marking.py",
    }
    assert set(d["public_interface"]) == {"owner_render_data", "replace_owner_render_data"}
    assert d["world_to_flat_oracle"] == "ae_engine/assembly_marking_geometry.py::backproject_mapped_skin_world_points"
    assert d["tolerance_authority"] == "ae_engine/contracts.py::PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES"
    assert "receiving_policy" not in d["scene_owner_responsibilities"]
    assert d["prohibited_ownership"]["receiving_joint_or_pairing_policy"] is True
    assert d["prohibited_ownership"]["new_backprojection_oracle"] is True
    assert d["prohibited_ownership"]["new_tolerance_source"] is True


def test_c2_deletion_proof_is_not_misrepresented_as_completed_c0_work():
    d = _decision()
    assert d["migration_ticket"] == 1384
    proof = d["c2_deletion_proof"]
    assert proof["status"] == "REQUIRED_FOR_C2_NOT_EXECUTED_IN_C0"
    assert proof["expected_production_consumers"] == 2
    assert proof["old_private_owner_functions_to_remove"] == [
        "_owner_render_data", "_replace_owner_render_data"
    ]
    assert proof["deleting_public_seam_must_fail_both_callers"] is True
    assert proof["no_shadow_compatibility_owner"] is True


def test_scene_identity_and_immutable_replacement_contract():
    d = _decision()
    behavior = d["immutable_replacement_contract"]
    assert behavior["direct_part_key"] == "exact_part_key"
    assert behavior["composite_part_key"] == "box_body:<role>"
    assert behavior["lookup_missing"] == "None"
    assert behavior["replace_missing"] == "KeyError"
    assert behavior["preserve_part_piece_order"] is True
    assert behavior["rebuild_composite_preview"] is True
    assert behavior["preserve_finalscene_metadata_diagnostics"] is True


def test_actual_two_callers_are_present_as_decision_evidence():
    d = _decision()
    for path in d["required_production_callers"]:
        assert (ROOT / path).is_file()
    assert (ROOT / "ae_engine/assembly_marking_geometry.py").is_file()
