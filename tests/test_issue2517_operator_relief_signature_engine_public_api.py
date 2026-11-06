# -*- coding: utf-8 -*-
"""#2517 operator Relief save/replay identity belongs solely to public Engine."""
from copy import deepcopy
import inspect
import json

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import (
    migrate_legacy_snapshot_joints, resolved_joint_graph_fingerprint,
)
from ae_engine.box_body_editor_readback import formed_box_body_fw_widths
from ae_engine.assembly_relief_state import (
    build_current_source_signature, committed_relief_cuts, source_matches_current,
)
from ae_engine.operator_relief_replay import (
    build_operator_current_relief_source_signature as owner,
)
from gui_modules.application import fold_designer_composition_state as gui


def _physical_source():
    scalar = {
        "model": "受電箱", "w": 800.0, "h": 1600.0,
        "d": 350.0, "t": 2.0, "fw": 29.0,
        "assembly_type": "INSERT",
    }
    joints = {"assembly_type": "INSERT", "assembly_joints": []}
    structure = {"active_type": "three_piece"}
    profile = [
        {"phase6_key": "fw_left", "len": 25.0, "angle": -90},
        {"phase6_key": "box_w", "len": 350.0, "core": "W"},
        {"phase6_key": "fw_right", "len": 25.0},
    ]
    parts = {"head": {"X": [{"phase6_key": "w", "len": 800.0}]}}
    return scalar, joints, structure, profile, parts


def test_public_engine_owner_matches_original_real_joint_and_formed_fw_signature():
    scalar, joints, structure, profile, parts = _physical_source()
    before = deepcopy((scalar, joints, structure, profile, parts))
    left, right = formed_box_body_fw_widths(profile, scalar["t"])
    expected = build_current_source_signature(
        scalar_source=scalar,
        joint_graph_fingerprint=resolved_joint_graph_fingerprint(
            migrate_legacy_snapshot_joints(joints)
        ),
        structure_state=structure,
        cabinet_family="受電箱",
        formed_left=left, formed_right=right,
        box_body_profile=profile, part_profiles=parts,
    )
    actual = api.build_operator_current_relief_source_signature(
        scalar_source=scalar, joint_state=joints,
        structure_state=structure, box_body_profile=profile, part_profiles=parts,
    )
    assert actual == expected
    assert actual["joint_graph_fingerprint"]
    assert actual["box_body_formed_fw"] == {"left": left, "right": right}
    assert (scalar, joints, structure, profile, parts) == before
    assert api.build_operator_current_relief_source_signature is owner
    assert ae_engine.build_operator_current_relief_source_signature is owner
    assert "build_operator_current_relief_source_signature" in ae_engine.__all__


def test_json_save_reload_preserves_relief_cut_and_rejects_stale_physical_source():
    scalar, joints, structure, profile, parts = _physical_source()
    kwargs = dict(scalar_source=scalar, joint_state=joints,
                  structure_state=structure, box_body_profile=profile,
                  part_profiles=parts)
    current = owner(**kwargs)
    saved = json.loads(json.dumps(current, ensure_ascii=False))
    assert source_matches_current(saved, current, ("head",))
    state = {
        "enabled": True, "source": saved,
        "parts": {"head": {
            "verified": True, "trust_level": "PROVISIONAL_3D",
            "cuts": [[(0, 0), (2, 0), (1, 2)]],
        }},
    }
    assert committed_relief_cuts(state, "head", current) == (
        ((0.0, 0.0), (2.0, 0.0), (1.0, 2.0)),
    )
    changed = owner(**dict(kwargs, scalar_source={**scalar, "w": 801.0}))
    assert not source_matches_current(saved, changed, ("head",))
    assert committed_relief_cuts(state, "head", changed) == ()
    modified_profile = deepcopy(profile)
    modified_profile[0]["len"] += 2.0
    changed_fold = owner(**dict(kwargs, box_body_profile=modified_profile))
    assert committed_relief_cuts(state, "head", changed_fold) == ()


@pytest.mark.parametrize("invalid_scalar,invalid_joints", (
    ([], {}), ({}, []), (None, {}),
))
def test_invalid_operator_sources_fail_closed(invalid_scalar, invalid_joints):
    _, _, structure, profile, parts = _physical_source()
    with pytest.raises(ValueError, match="RELIEF_.*_MAPPING_REQUIRED"):
        owner(
            scalar_source=invalid_scalar, joint_state=invalid_joints,
            structure_state=structure, box_body_profile=profile,
            part_profiles=parts,
        )


def test_gui_only_passes_operator_inputs_to_public_relief_source_api():
    source = inspect.getsource(gui.current_relief_source_signature)
    assert "manufacturing_api.build_operator_current_relief_source_signature(" in source
    assert "resolved_joint_graph_fingerprint(" not in source
    assert "migrate_legacy_snapshot_joints(" not in source
    assert "formed_box_body_fw_widths(" not in source
    assert "manufacturing_api.build_current_source_signature(" not in source
