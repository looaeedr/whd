from __future__ import annotations

from pathlib import Path


MIGRATED = (
    "test_resolved_manufacturing_bridge.py",
    "test_phase6_corner_dimension_controls.py",
    "test_phase6_assembly_3d_view.py",
    "test_overlay_formed_fw_registry_contract.py",
    "test_overlay_fw_width_invariant.py",
    "test_phase6_3d_retain_and_baseline.py",
    "test_joint_diagnostics_contract.py",
    "test_certified_relief_runtime_contract.py",
)


def test_issue1062_retired_finalscene_bridge_oracles_do_not_regrow():
    for name in MIGRATED:
        source = (Path("tests") / name).read_text(encoding="utf-8")
        assert "_phase6_query_assembly_render_data" not in source, name
        assert "_phase6_active_mesh_profiles" not in source, name


def test_issue1062_tests_use_current_finalscene_adapter_and_profile_seam():
    sources = {name: (Path("tests") / name).read_text(encoding="utf-8") for name in MIGRATED}
    query_sources = [text for text in sources.values() if "query_assembly_render_data()" in text]
    assert len(query_sources) >= 6
    assert all("_phase6_final_scene_adapter(" in text for text in query_sources)
    combined = "\n".join(sources.values())
    assert "_phase6_mesh_profiles_for_part" in combined


def test_issue1062_current_bridge_exposes_successor_finalscene_seams_only():
    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    assert "def _phase6_final_scene_adapter(" in source
    assert "def _phase6_mesh_profiles_for_part(" in source
    assert "def _phase6_query_assembly_render_data(" not in source
    assert "def _phase6_active_mesh_profiles(" not in source
