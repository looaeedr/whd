# -*- coding: utf-8 -*-
"""NFB page is a subtransaction; main Confirm All owns physical/version writes."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from gui_modules.application.receiving_inner_door_hole_editor import (
    inner_door_commit_target, open_inner_door_hole_editor,
)
from ae_engine.cabinet_types import policy
from ae_engine.sheetmetal_features import RectFeature, FeatureAnchor, Vec2
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_receiving_modes import fresh_receiving_mode


@pytest.mark.parametrize("entered_from,expected", [
    (None, "physical"),
    ("single", "physical"),
    ("candidate", "candidate"),
])
@pytest.mark.parametrize("project_mode", ["set_bay", "quantity"])
def test_save_target_uses_entry_not_project_mode(entered_from, expected, project_mode):
    # A project can have saved Set/Bay rows while this editor was opened from
    # its physical part. It must NEVER quietly turn into candidate X.
    project = fresh_receiving_mode(project_mode, {
        "w": 800, "h": 1600, "d": 350, "t": 2,
    })
    assert project["active_mode"] == project_mode
    assert inner_door_commit_target(entered_from) == expected


def test_unknown_save_entry_fails_closed():
    with pytest.raises(ValueError, match="未知"):
        inner_door_commit_target("set_bay-data")


def _enter_editor(project_mode, *, settings_mode=None):
    original = fresh_receiving_mode(project_mode, {
        "w": 800, "h": 1600, "d": 350, "t": 2,
    })
    part = policy.derive_inner_door_panels(original)[0].stable_id
    workspace = Phase6DesignerWorkspace.from_snapshot({
        **original, "existing_parts": ["box_body", part],
        "active_part": part,
    })
    saved_candidates = deepcopy(original.get("receiving_inner_door_candidates"))
    writes, payloads, confirmed = [], [], []

    class Host:
        def scene_query(self, *_args):
            return None
        def _open_unified_hole_editor(self, *_args, **kwargs):
            payloads.append(kwargs)
            self.last_unified_hole_editor = SimpleNamespace(
                _receiving_config_frame=None, _receiving_staged_config=None,
            )
            return self.last_unified_hole_editor

    host = Host()
    app = SimpleNamespace(
        root=SimpleNamespace(),
        designer_workspace=workspace,
        _phase6_input_snapshot=original,
        _scene_query_callback=host.scene_query,
        _load_part_holes=lambda *_: writes.append("redraw"),
        submit_update_intent=lambda *_a, **_k: writes.append("commit"),
    )
    target = open_inner_door_hole_editor(
        app, part, settings_mode=settings_mode,
        **({"on_settings_confirm": lambda p, features, config:
            confirmed.append((p, features, config))}
           if settings_mode == "candidate" else {}),
    )
    return (original, saved_candidates, workspace, part, target,
            payloads[0], writes, confirmed)


def _example_hole():
    return RectFeature(
        width=57, height=96,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(120, 150),
    )


def test_ordinary_board_entry_in_multi_project_still_commits_physical_only():
    (snapshot, original_candidates, workspace, part, editor, payload,
     writes, confirmed) = _enter_editor("set_bay")
    assert not hasattr(editor, "_receiving_settings_mode")
    hole = _example_hole()
    payload["feature_list_override"].append(hole)
    payload["sync_callback"]()  # NFB tab stage cannot write the real board.
    assert workspace.features_for(part) == []
    assert writes == []
    assert snapshot.get("receiving_inner_door_candidates") == original_candidates
    # Native Main Confirm All is the ONLY persistence callback.
    payload["on_confirm_features"]([hole])
    assert workspace.features_for(part) == [hole]
    assert snapshot.get("receiving_inner_door_candidates") == original_candidates
    assert confirmed == []
    assert writes == ["redraw", "commit"]


def test_cancel_before_main_confirm_preserves_previous_board_and_candidates():
    (snapshot, original_candidates, workspace, part, editor, payload,
     writes, confirmed) = _enter_editor("set_bay")
    original_hole = _example_hole()
    workspace.stash_features(part, [original_hole])
    pending = RectFeature(25, 30, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(230, 290))
    payload["feature_list_override"].append(pending)
    payload["sync_callback"]()
    # The outer editor's Cancel All never invokes on_confirm_features.
    assert workspace.features_for(part) == [original_hole]
    assert snapshot.get("receiving_inner_door_candidates") == original_candidates
    assert writes == [] and confirmed == []


def test_explicit_multi_entry_never_saves_before_main_confirm():
    (snapshot, original_candidates, workspace, part, editor, payload,
     writes, confirmed) = _enter_editor("set_bay", settings_mode="candidate")
    feature = _example_hole()
    assert editor._receiving_settings_mode == "candidate"
    payload["feature_list_override"].append(feature)
    payload["sync_callback"]()
    assert writes == [] and confirmed == []
    assert workspace.features_for(part) == []
    payload["on_confirm_features"]([feature])
    # The candidate/version owner is invoked only from Main Confirm All;
    # no mutation to a live panel, no premature version write.
    assert confirmed == [(part, [feature], None)]
    assert workspace.features_for(part) == []
    assert snapshot.get("receiving_inner_door_candidates") == original_candidates


def test_embedded_tab_source_routes_only_to_staged_main_not_candidate_write():
    # Verify the composition has ONE tab-stage closure for every editor entry.
    # This guards against reintroducing the old set_bay/window-exists heuristic.
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/application/fold_designer_composition_receiving.py"
              ).read_text(encoding="utf-8")
    assert 'entry_mode = (getattr(embed_parent.winfo_toplevel(),' in source
    assert 'inner_door_commit_target(entry_mode)' in source
    assert 'if embed_parent is not None:' in source
    assert 'stage_in_editor(config, openings)' in source
    assert 'if not callable(stage_in_editor):' in source
    assert 'go_to_main_tab()' in source
    assert 'multi_entry = bool(' not in source
    assert 'if direct_to_drawing:' not in source
    # The embedded NFB transaction MUST return before the standalone
    # version manager's candidate persistence branch can run.
    stage = source.index('stage_in_editor(config, openings)')
    manager = source.index('persist_inner(saved)', stage)
    assert stage < source.index('return', stage) < manager
