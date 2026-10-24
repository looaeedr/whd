# -*- coding: utf-8 -*-
"""#1504 SWT-AC-12: CSV V5 NFB staging must not mutate existing owners.

This is a cross-owner mutation regression, NOT manufacturing approval:
unapproved absolute X/Y, MFG-2, and Windows operator UAT still hold.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine.cabinet_types import policy, receiving
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.inner_door_frames import derive_inner_door_frames
from ae_engine.manufacturing_api import (
    build_inner_door_panel_render_data, build_part_render_data,
)
from ae_engine.receiving_nfb_csv_editor_features import editor_nfb_features_from_csv
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.sheetmetal_drawing import CirclePrimitive
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
from tests.test_issue1502_receiving_existing_base_plate_patterns import _spec
from tests.test_issue510_receiving_back_panel_modes import _contract, _render


def _w800():
    state = receiving.apply_family_defaults({
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    state.update({
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    })
    return state


def _physical_baseline(state):
    panels = policy.derive_inner_door_panels(state)
    assert len(panels) == 1
    panel = panels[0]
    frames = derive_inner_door_frames(
        "upper", spans={"top": panel.width, "left": panel.height,
                        "right": panel.height},
        thickness=panel.thickness, included_sides=("top", "left", "right"),
    )
    divider = derive_box_body_dividers(
        ((800.0, (1100.0, 500.0)),), depth=state["d"],
        thickness=state["t"], layout_scope="receiving-main",
        handle_edges={}, model_name="受電箱",
    )[0]
    base = build_part_render_data(_spec(RECEIVING_BASE_PATTERN_CENTER))
    rear = tuple(
        (mode, tuple(_contract(mode)["fixed_slot_datums"]),
         _contract(mode)["opening"])
        for mode in ("FULL", "HALF", "BACK_OPENING")
    )
    return {
        "panel": panel,
        "panel_primitives": tuple(build_inner_door_panel_render_data(panel).scene.primitives),
        "frame_contracts": tuple(
            (f.stable_id, f.material_lengths, f.signed_fold_chain, f.blank_width)
            for f in frames
        ),
        "divider": (divider.material_lengths, divider.signed_fold_chain, divider.span),
        "base_bounds": tuple(base.material.bounds),
        "base_mfg2_approved": base.metadata["receiving_nfb_base_mfg2_release_approved"],
        "base_primitives": tuple(base.scene.primitives),
        "rear": rear,
    }


def test_swt12_current_csv_v5_stage_never_changes_inner_frame_base_divider_or_rear_owners():
    state = _w800()
    original = deepcopy(state)
    baseline = _physical_baseline(state)
    model = numeric_model_ref("士林", "2P400")
    draft = {
        "layers": 1, "layer_heights_mm": [550.0, 800.0],
        "models": [model, ""],
    }

    # This invokes WHD's real original Hole Editor CSV staging adapter, not
    # an invented DXF or a stand-in hole-position formula.
    staged = editor_nfb_features_from_csv(state, draft)
    assert len(staged) == 1
    assert staged[0].source_type == "NFB_CSV_SOURCE"
    assert staged[0].layer == "CUTTING"
    assert state == original
    assert _physical_baseline(state) == baseline

    assert baseline["panel"].fold_left == baseline["panel"].fold_right == 19.0
    assert baseline["panel"].fold_top == baseline["panel"].fold_bottom == 19.0
    assert baseline["panel"].thickness == 2.0
    assert baseline["frame_contracts"][1][1] == (22.0, 46.0, 22.0)
    assert baseline["frame_contracts"][2][1] == (22.0, 20.0, 46.0, 22.0)
    assert baseline["divider"][2] == pytest.approx(796.0)
    assert baseline["base_bounds"] == pytest.approx((0.0, 0.0, 772.0, 240.0))
    assert baseline["base_mfg2_approved"] is False
    assert len(baseline["rear"]) == 3
    assert all(len(slots) == 4 for _, slots, _ in baseline["rear"])
    assert baseline["rear"][2][2] is not None


def test_swt12_current_nfb_staging_does_not_change_original_vault_family():
    import fold_designer_bridge as bridge

    state = _w800()
    vault = {
        "model": "金庫型", "w": 400.0, "h": 600.0, "d": 250.0,
        "t": 2.0, "fw": 25.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "multi_door_enabled": False, "part_dimensions": {},
    }
    before = deepcopy(vault)
    from types import SimpleNamespace
    holder = SimpleNamespace(
        _settings_values=deepcopy(vault),
        _phase6_input_snapshot=vault,
    )
    original = bridge._phase6_recalculate_part_dimensions(holder)
    editor_nfb_features_from_csv(state, {
        "layers": 1, "layer_heights_mm": [550.0, 800.0],
        "models": [numeric_model_ref("士林", "2P400"), ""],
    })
    after = bridge._phase6_recalculate_part_dimensions(holder)
    assert vault == before
    assert original["door"] == pytest.approx({"width": 335.0, "height": 535.0})
    assert after == original



def test_swt12_actual_workspace_inner_door_csv_confirm_preserves_other_physical_owners():
    """A confirmed original-editor hole belongs to the inner panel only."""
    from phase6_designer_workspace import Phase6DesignerWorkspace

    state = _w800()
    panel = policy.derive_inner_door_panels(state)[0]
    state.update({
        "active_mode": "quantity",
        "existing_parts": [
            "box_body", "head", "tail", "door", "base_plate",
            panel.stable_id,
        ],
        "active_part": panel.stable_id,
    })
    original_geometry = _physical_baseline(state)
    workspace = Phase6DesignerWorkspace.from_snapshot(state)
    before = workspace.part_features_snapshot()
    staged = editor_nfb_features_from_csv(state, {
        "layers": 1,
        "layer_heights_mm": [550.0, 800.0],
        "models": [numeric_model_ref("士林", "2P400"), ""],
    })
    assert len(staged) == 1
    assert dict(staged[0].source_params)["placement"] == "native_editor_initial"
    assert "absolute_x_mm" not in dict(staged[0].source_params)

    baseline_inner = build_inner_door_panel_render_data(panel)
    confirmed_inner = build_inner_door_panel_render_data(panel, features=staged)
    assert confirmed_inner.metadata["inner_door_hole_feature_count"] == 1
    assert tuple(confirmed_inner.fold_guides) == tuple(baseline_inner.fold_guides)
    assert tuple(confirmed_inner.scene.primitives) != tuple(baseline_inner.scene.primitives)

    workspace.stash_features(panel.stable_id, staged)
    assert workspace.features_for(panel.stable_id) == list(staged)
    saved = workspace.part_features_snapshot()
    for owner in ("box_body", "head", "tail", "door", "base_plate"):
        assert saved.get(owner, []) == before.get(owner, [])
        assert workspace.features_for(owner) == before.get(owner, [])
    # Derive real physical owners from the committed Workspace snapshot,
    # not from the untouched input (which would make this regression vacuous).
    committed = deepcopy(state)
    committed.update(workspace.snapshot())
    assert committed["part_features"][panel.stable_id] == list(staged)
    assert _physical_baseline(committed) == original_geometry
    assert all(k == panel.stable_id or saved[k] == before.get(k, [])
               for k in saved)


@pytest.mark.parametrize("thickness", [1.0, 1.5, 2.0, 3.0])
def test_swt12_last_22_mating_flange_and_46_plus_2t_formed_occupation(thickness):
    from ae_engine.inner_door_frames import inner_door_frame_formed_occupation

    frames = derive_inner_door_frames(
        "upper", spans={"top": 800.0, "left": 1100.0, "right": 1100.0},
        thickness=thickness, included_sides=("top", "left", "right"),
    )
    assert len(frames) == 3
    assert inner_door_frame_formed_occupation(thickness) == pytest.approx(
        46.0 + 2.0 * thickness
    )
    assert {f.side for f in frames} == {"top", "left", "right"}
    assert all(f.material_lengths[-2:] == (46.0, 22.0) for f in frames)
    assert all(f.material_lengths[-1] == 22.0 for f in frames)
    assert all(f.thickness == thickness for f in frames)


def test_swt12_nonphysical_thickness_cannot_claim_frame_occupation():
    from ae_engine.inner_door_frames import inner_door_frame_formed_occupation

    with pytest.raises(ValueError, match="positive"):
        inner_door_frame_formed_occupation(0)
