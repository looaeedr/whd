from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")

ZERO_EXTERNAL_CONSUMER_IMPORTS = {
    "flush_fold_designer_update_intents",
    "apply_fold_designer_settings_delta",
    "sync_snapshot_intent_joints",
    "FourCornerTypePolicy",
    "policy_from_corner_state",
    "DiagnosticSnapshotContext",
    "build_active_diagnostic_snapshot",
    "_project_assembly_scene_render_data",
    "AssemblySceneRenderData",
    "_phase6_apply_resolved_cut_to_owner",
    "_phase6_side_wrap_target_corners",
    "_phase6_expand_box_body_fw_world_mid",
    "_phase6_shift_multistage_terminal_fold_world_mid",
    "_phase6_joint_relief_state_item_matches",
    "_phase6_cut_geometry_from_state_item",
    "_phase6_signature_canonical_value",
}


def _import_bindings() -> set[str]:
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"), filename=str(BRIDGE))
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                out.add(alias.asname or alias.name)
    return out


def test_c0_zero_external_consumer_import_reexports_are_removed():
    remaining = ZERO_EXTERNAL_CONSUMER_IMPORTS & _import_bindings()
    assert not remaining, (
        "C0 RED: zero-external-consumer bridge import re-exports remain: "
        f"{sorted(remaining)}"
    )
