# -*- coding: utf-8 -*-
from pathlib import Path

import pytest


def _overlay_snapshot():
    return {
        "w": 400, "d": 250, "t": 2, "fw": 25,
        "assembly_type": "INSERT",
        "corner_state": {
            "head": {
                "top_left": {"type_id": "OVERLAY", "amount_t": 1.0},
                "top_right": {"type_id": "OVERLAY", "amount_t": 1.5},
            },
            "tail": {
                "top_left": {"type_id": "OVERLAY", "amount_t": 2.0},
                "top_right": {"type_id": "OVERLAY", "amount_t": 1.0},
            },
        },
    }


def _five_segment_box():
    return [
        {"len": 25.0, "angle": -90.0, "phase6_key": "fw_left"},
        {"len": 246.0, "angle": -90.0, "core": "D", "phase6_key": "d_left"},
        {"len": 396.0, "angle": -90.0, "core": "W", "phase6_key": "w"},
        {"len": 246.0, "angle": -90.0, "core": "D", "phase6_key": "d_right"},
        {"len": 25.0, "phase6_key": "fw_right"},
    ]


def test_endcap_semantics_module_owns_assembly_and_fw_rules():
    import phase6_endcap_semantics as semantics
    from ae_engine.sheetmetal_geometry import CornerTypeId

    snapshot = _overlay_snapshot()
    assert semantics.resolve_box_assembly_type(snapshot) is CornerTypeId.INSERT

    state = semantics.normalize_endcap_fw_state(snapshot)
    semantics.set_endcap_fw_follow(state, "head", False, box_fw=25.0)
    semantics.set_endcap_fw_override(state, "head", 31.0)
    snapshot["fw"] = 30.0

    assert semantics.resolve_endcap_fw(snapshot, "head", state=state) == pytest.approx(31.0)
    assert semantics.resolve_endcap_fw(snapshot, "tail", state=state) == pytest.approx(30.0)


def test_bridge_reexports_endcap_semantics_without_second_behavior():
    import fold_designer_bridge as bridge
    import phase6_endcap_semantics as semantics

    assert bridge.resolve_box_assembly_type is semantics.resolve_box_assembly_type
    assert bridge.normalize_endcap_fw_state is semantics.normalize_endcap_fw_state
    assert bridge.set_endcap_fw_follow is semantics.set_endcap_fw_follow


def test_fold_profile_module_owns_linked_chain_and_overlay_flat_x():
    import phase6_fold_profiles as profiles

    snapshot = _overlay_snapshot()
    snapshot["assembly_type"] = "OVERLAY"
    snapshot.update({"yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15})
    endcap = profiles.build_endcap_xy_profiles(snapshot, part_key="head")
    assert [row.get("phase6_key") for row in endcap["X"]] == ["endcap_w_flat"]
    assert endcap["X"][0]["len"] == pytest.approx(400.0)

    snapshot["corner_state"] = {}
    snapshot["assembly_type"] = "INSERT_OVERLAY"
    linked = profiles.build_linked_endcap_xy_profiles(snapshot, _five_segment_box())
    assert [row.get("phase6_key") for row in linked["head"]["Y"]] == [
        "fw", "endcap_d_core", "ybottom1"
    ]
    assert [row.get("phase6_key") for row in linked["tail"]["Y"]] == [
        "ybottom1", "endcap_d_core", "fw"
    ]


def test_bridge_reexports_fold_profile_functions_without_wrappers():
    import fold_designer_bridge as bridge
    import phase6_fold_profiles as profiles

    assert bridge.build_endcap_xy_profiles is profiles.build_endcap_xy_profiles
    assert bridge.build_linked_endcap_xy_profiles is profiles.build_linked_endcap_xy_profiles
    assert bridge.profile_to_fold_segments is profiles.profile_to_fold_segments


def test_production_gui_imports_domain_owners_not_bridge_for_semantics():
    import ast

    tree = ast.parse(Path("gui.py").read_text(encoding="utf-8"))
    imported_from_bridge = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge"
        for alias in node.names
    }
    forbidden = {
        "profile_to_fold_segments",
        "build_endcap_xy_profiles",
        "build_linked_endcap_xy_profiles",
        "resolve_box_assembly_type",
        "ASSEMBLY_TYPE_LABELS",
        "ASSEMBLY_LABEL_TO_TYPE",
        "normalize_endcap_fw_state",
        "resolve_endcap_fw",
        "set_endcap_fw_follow",
        "set_endcap_fw_override",
    }
    assert imported_from_bridge == {"Phase6FoldDesignerApp"}
    assert not forbidden.intersection(imported_from_bridge)


def test_bridge_does_not_redefine_extracted_domain_functions():
    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    forbidden_defs = (
        "normalize_endcap_fw_state",
        "resolve_endcap_fw",
        "set_endcap_fw_follow",
        "set_endcap_fw_override",
        "resolve_box_assembly_type",
        "apply_box_assembly_type_to_raw_state",
        "build_box_body_profile",
        "build_endcap_xy_profiles",
        "read_endcap_xy_profiles",
        "build_linked_endcap_xy_profiles",
        "merge_box_body_profile",
        "profile_to_fold_segments",
    )
    for name in forbidden_defs:
        assert f"def {name}(" not in source


def test_bridge_exposes_one_orchestration_seam_for_legacy_wrappers():
    import fold_designer_bridge as bridge

    for name in (
        "submit_update_intent",
        "apply_settings_delta",
        "switch_active_part",
        "publish_if_changed",
    ):
        assert hasattr(bridge.Phase6FoldDesignerApp, name), name


def test_preview_aware_legacy_wrapper_only_submits_intent():
    import inspect
    import fold_designer_bridge as bridge

    source = inspect.getsource(bridge._phase6_preview_aware_do_update)
    assert "submit_update_intent" in source
    assert "_PHASE6_RENDERING_DO_UPDATE" not in source
    assert ".renderer.render" not in source
