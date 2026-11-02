"""#2517 Physical Receiving Bay preview cache eligibility and world offsets use Engine."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    project_receiving_bay_legacy_aliases,
)
from gui_modules.application.fold_designer_composition_receiving import (
    _receiving_bay_preview_fingerprint_snapshot as gui_key,
    _receiving_rebase_preview_world_offsets as gui_rebase,
)
from phase6_final_scene_contracts import (
    AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
)


def _snapshot():
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=4,
    )
    return {"model": "受電箱", "active_mode": "set_bay",
            "receiving_layout": layout}


def test_real_bay_dependency_projection_is_exact_engine_and_legacy_parity():
    snapshot = _snapshot()
    before = deepcopy(snapshot)
    arguments = dict(set_index=0, bay_index=0, allow_suffix_topology_reuse=True)
    direct = api.project_receiving_bay_preview_fingerprint_snapshot(
        snapshot, **arguments,
    )
    assert direct == gui_key(snapshot, **arguments)
    assert snapshot == before
    changed = {
        **snapshot,
        "receiving_layout": update_receiving_bay(
            snapshot["receiving_layout"], set_index=0, bay_index=3,
            width=900, height=1800, depth=400,
        ),
    }
    assert api.project_receiving_bay_preview_fingerprint_snapshot(
        changed, **arguments,
    ) == direct
    adjacent = {
        **snapshot,
        "receiving_layout": update_receiving_bay(
            snapshot["receiving_layout"], set_index=0, bay_index=1, width=900,
        ),
    }
    assert api.project_receiving_bay_preview_fingerprint_snapshot(
        adjacent, **arguments,
    ) != direct


def test_unknown_custom_joint_and_other_family_never_reuse_omitted_dependencies():
    raw = _snapshot()
    candidate = {**raw, "assembly_joints": [{"subject_part": "unknown"}]}
    got = api.project_receiving_bay_preview_fingerprint_snapshot(
        candidate, set_index=0, bay_index=0,
    )
    assert got["assembly_joints"] == candidate["assembly_joints"]
    assert "width" in got["receiving_layout"]["sets"][0]["bays"][3]
    for model in ("金庫型", "unsupported"):
        other = {**raw, "model": model}
        assert api.project_receiving_bay_preview_fingerprint_snapshot(
            other, set_index=0, bay_index=0,
        ) == other


def test_engine_preview_translation_matches_immutable_gui_scene_and_rejects_unsafe():
    material = object()
    original = AssemblyScenePart(
        part_key="box_body", render_data=material,
        x_profile=(), y_profile=(), offset=(5.0, 2.0, 0.0),
    )
    scene = AssemblySceneRenderData(
        assembly_parts=(original,), preserve_endcap_core_origin=True,
    )
    view = FinalSceneViewRequest(
        render_data=scene, x_profile=(), y_profile=(), part_key="assembly",
    )
    positions = api.plan_receiving_bay_preview_offset_rebase(
        scene.assembly_parts, (0, 0, 0), (10, -4, 3),
    )
    assert positions == ((15.0, -2.0, 3.0),)
    moved = gui_rebase(view, (0, 0, 0), (10, -4, 3))
    assert moved.render_data.assembly_parts[0].offset == positions[0]
    assert original.offset == (5.0, 2.0, 0.0)
    assert moved.render_data.assembly_parts[0].render_data is material
    assert api.plan_receiving_bay_preview_offset_rebase(
        (original,), (0, 0, 0), (float("nan"), 0, 0),
    ) is None
    assert api.plan_receiving_bay_preview_offset_rebase(
        (SimpleNamespace(offset=(0, 0, 0), placement="standalone"),),
        (0, 0, 0), (1, 0, 0),
    ) is None
    unsafe = FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(
            assembly_parts=(original,), preserve_endcap_core_origin=True,
            show_interference=True,
        ), x_profile=(), y_profile=(), part_key="assembly",
    )
    assert gui_rebase(unsafe, (0, 0, 0), (1, 0, 0)) is None


def test_gui_retains_compatibility_but_drops_domain_calculation_and_engine_has_no_reverse_import():
    root = Path(__file__).resolve().parents[1]
    code = (root / "gui_modules/application/fold_designer_composition_receiving.py").read_text(encoding="utf-8")
    between = code.split("def _receiving_bay_preview_face_features_key(")[1].split(
        "def _receiving_cached_bay_inner_door_panel(")[0]
    assert "manufacturing_api." in between
    assert "shallow_layout" not in between
    assert "for position in hidden" not in between
    engine = (root / "ae_engine/receiving_bay_preview_source.py").read_text(encoding="utf-8")
    assert "from gui_modules" not in engine and "from phase6_" not in engine
