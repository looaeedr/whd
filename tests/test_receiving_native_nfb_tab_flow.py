# -*- coding: utf-8 -*-
"""Receiving tab -> native Hole Editor NFB staging, no nested CSV popup."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from ae_engine.sheetmetal_geometry import Vec2

import pytest

from ae_engine.receiving_nfb_csv_editor_features import editor_nfb_features_from_csv
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from ae_engine.cabinet_types import policy
from phase6_project_file import _decode, _encode
from phase6_receiving_modes import fresh_receiving_mode


ROOT = Path(__file__).resolve().parents[1]


def _physical():
    return fresh_receiving_mode("quantity", {
        "w": 800, "h": 1600, "d": 350, "t": 2,
    })


def _config(*, layers=1, heights=(550, 800), first=1, second=0):
    model = numeric_model_ref("士林", "2P400")
    return {
        "layers": layers, "layer_heights_mm": list(heights),
        "models": [
            [model] * first if first != 1 else model if first else "",
            [model] * second if second != 1 else model if second else "",
        ],
    }


def _hole_center(hole):
    xs = [p.x for p in hole.points]
    ys = [p.y for p in hole.points]
    return ((min(xs) + max(xs))/2, (min(ys) + max(ys))/2)


def test_first_row_csv_nfb_draft_has_real_source_outline_at_operator_y():
    physical = _physical()
    panel = policy.derive_inner_door_panels(physical)[0]
    holes = editor_nfb_features_from_csv(physical, _config())
    assert len(holes) == 1
    hole = holes[0]
    assert hole.layer == "CUTTING"
    assert hole.source_type == "NFB_CSV_SOURCE"
    assert dict(hole.source_params)["model"] == "2P400"
    assert dict(hole.source_params)["part_id"] == panel.stable_id
    assert len(dict(hole.source_params)["csv_sha256"]) == 64
    assert hole.anchor.value == "absolute_finished_face"
    assert hole.points[1].x - hole.points[0].x == pytest.approx(57)
    assert hole.points[2].y - hole.points[1].y == pytest.approx(96)
    projection = project_nfb_inner_door_nominal_y(
        dict(physical, receiving_inner_door_layer_heights_mm=[550, 800]),
        panel.inner_door_id, layer_count=1, slot_index=0,
    )
    assert _hole_center(hole)[1] == pytest.approx(
        projection.unfolded_uv_y_mm - (panel.fold_bottom - panel.thickness)
    )
    assert _decode(_encode(holes))[0] == hole


def test_two_rows_stage_distinct_real_holes_and_first_row_300():
    physical = _physical()
    config = _config(layers=2, heights=(300, 800), second=1)
    holes = editor_nfb_features_from_csv(physical, config)
    assert len(holes) == 2
    assert _hole_center(holes[0])[1] > _hole_center(holes[1])[1]
    assert [dict(f.source_params)["layer_index"] for f in holes] == [0, 1]
    assert [dict(f.source_params)["model"] for f in holes] == ["2P400", "2P400"]


def test_multiple_csv_switches_have_separate_editable_staging_centers():
    holes = editor_nfb_features_from_csv(
        _physical(), _config(first=3),
    )
    assert len(holes) == 3
    assert len(set(_hole_center(hole)[0] for hole in holes)) == 3
    assert all(hole.source_type == "NFB_CSV_SOURCE" for hole in holes)


def test_empty_csv_selection_stages_no_holes_and_does_not_mutate_snapshot():
    physical = _physical()
    before = deepcopy(physical)
    holes = editor_nfb_features_from_csv(
        physical, _config(first=0),
    )
    assert holes == ()
    assert physical == before


def test_second_row_invalid_height_or_missing_source_fails_atomically():
    with pytest.raises(ValueError):
        editor_nfb_features_from_csv(
            _physical(), _config(layers=2, heights=(1200, 1300), second=1),
        )
    wrong = _config()
    wrong["models"][0] = "missing-model.dxf"
    with pytest.raises(ValueError, match="CSV 型號"):
        editor_nfb_features_from_csv(_physical(), wrong)


def test_tab_flow_uses_native_undoable_stage_and_preserves_confirm_owner():
    receiving = (
        ROOT / "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    composition = (
        ROOT / "gui_modules/editors/hole_editor_composition.py"
    ).read_text(encoding="utf-8")
    assert "initial[\"layer_heights_mm\"] = [550.0, 800.0]" not in receiving
    assert 'SETTING_DEFAULTS["inner_door_layer_heights_mm"]' in receiving
    assert 'layer_height_vars[0].set("300")' not in receiving
    assert "transition_receiving_nfb_layer_heights(" in receiving
    assert "stage_in_editor(config, openings)" in receiving
    assert "accept(openings)" in receiving
    assert "go_to_main_tab()" in receiving
    assert "editor._receiving_stage_selected_nfb_openings" in composition
    assert "HoleEditorAction.preview_all(" in composition
    assert "on_confirm_features" in composition
    assert "CSV 開口位置" not in receiving
    assert "檢查 CSV 開口" not in receiving
    assert "open_nfb_world_x_dialog" not in receiving


def test_one_and_two_tier_height_defaults_follow_single_rule_without_losing_custom_y():
    from ae_engine.receiving_shared_settings import (
        default_receiving_nfb_layer_heights,
        transition_receiving_nfb_layer_heights,
    )

    assert default_receiving_nfb_layer_heights(1) == [550.0, 830.0]
    assert default_receiving_nfb_layer_heights(2) == [330.0, 830.0]
    assert transition_receiving_nfb_layer_heights(
        [550.0, 830.0], old_count=1, new_count=2,
    ) == [330.0, 830.0]
    assert transition_receiving_nfb_layer_heights(
        [330.0, 830.0], old_count=2, new_count=1,
    ) == [550.0, 830.0]
    assert transition_receiving_nfb_layer_heights(
        [610.0, 830.0], old_count=1, new_count=2,
    ) == [610.0, 830.0]
    assert transition_receiving_nfb_layer_heights(
        [325.0, 830.0], old_count=2, new_count=1,
    ) == [325.0, 830.0]
    with pytest.raises(ValueError):
        default_receiving_nfb_layer_heights(0)
    with pytest.raises(ValueError):
        transition_receiving_nfb_layer_heights(
            [float("nan"), 830.0], old_count=1, new_count=2,
        )


def test_reenter_receiving_tab_preserves_manually_moved_native_hole():
    physical = _physical()
    base = editor_nfb_features_from_csv(physical, _config())
    moved = replace(base[0], offset=Vec2(12.0, 24.0))
    unchanged = editor_nfb_features_from_csv(
        physical, _config(), current_features=(moved,),
    )
    assert unchanged == (moved,)
    shifted = editor_nfb_features_from_csv(
        physical, _config(heights=(500, 800)), current_features=(moved,),
    )
    assert shifted[0].offset.x == pytest.approx(12.0)
    assert shifted[0].offset.y == pytest.approx(74.0)
    assert dict(shifted[0].source_params)["y_from_top_mm"] == 500.0


def test_generic_inner_door_entry_never_writes_before_native_confirm_all():
    from types import SimpleNamespace
    from ae_engine.sheetmetal_features import RectFeature, FeatureAnchor
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from gui_modules.application.receiving_inner_door_hole_editor import (
        open_inner_door_hole_editor,
    )
    physical = _physical()
    part = policy.derive_inner_door_panels(physical)[0].stable_id
    workspace = Phase6DesignerWorkspace.from_snapshot({
        **physical, "existing_parts": ["box_body", part],
        "active_part": part,
    })
    payloads, writes = [], []

    class Host:
        def scene_query(self, *_args):
            return None

        def _open_unified_hole_editor(self, *_args, **kwargs):
            payloads.append(kwargs)
            self.last_unified_hole_editor = SimpleNamespace()
            return self.last_unified_hole_editor

    host = Host()
    app = SimpleNamespace(
        root=SimpleNamespace(),
        designer_workspace=workspace,
        _phase6_input_snapshot=physical,
        _scene_query_callback=host.scene_query,
        _load_part_holes=lambda *_args: writes.append("load"),
        submit_update_intent=lambda *_args, **_kwargs: writes.append("commit"),
    )
    open_inner_door_hole_editor(app, part)
    pending = RectFeature(
        width=25.0, height=111.0,
        anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0),
    )
    payloads[0]["feature_list_override"].append(pending)
    payloads[0]["sync_callback"]()
    assert workspace.features_for(part) == []
    assert writes == []
    payloads[0]["on_confirm_features"]([pending])
    assert workspace.features_for(part) == [pending]
    assert "commit" in writes


@pytest.mark.parametrize("invalid", (
    (True,), (False,), (0, True), (0, []), ([],),
    None, 0, ("1",), (-1,), (99,),
))
def test_ac28_inner_candidate_invalid_highlight_cannot_apply_to_other_bays(invalid):
    """Corrupt multi-Bay highlight must not alias boolean as Bay 1 or mutate."""
    from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter

    initial = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )
    adapter = ReceivingSetBayAdapter(initial)
    original = adapter.layout
    selection = adapter.selection
    with pytest.raises(ValueError, match="高亮有效的連"):
        adapter.apply_inner_door_candidate_to_bays(
            _config(), 0, invalid, version_id="inner-door-v1",
        )
    assert adapter.layout == original
    assert adapter.selection == selection


def test_ac28_inner_candidate_valid_highlight_is_atomic_and_preserves_neighbor():
    from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
    from ae_engine.receiving_shared_settings import setting_value
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter

    initial = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )
    adapter = ReceivingSetBayAdapter(initial)
    before = adapter.layout
    source = _config()
    selected = adapter.apply_inner_door_candidate_to_bays(
        source, 0, (2, 0), version_id="inner-door-v1",
    )
    after = adapter.layout
    assert selected == (0, 2)
    assert adapter.selection.bay_index == 0
    assert after["sets"][0]["bays"][1] == before["sets"][0]["bays"][1]
    assert setting_value(after["sets"][0], 1, "inner_door_version_id") is None
    for bay_index in (0, 2):
        assert setting_value(
            after["sets"][0], bay_index, "inner_door_version_id"
        ) == "inner-door-v1"
    assert before == initial
