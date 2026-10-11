"""Receiving Hole Editor candidate persistence, independence and safe transactions."""
from __future__ import annotations

from copy import deepcopy
import pytest

from ae_engine.receiving_hole_candidates import (
    normalize_candidates, create_candidate, update_candidate,
    delete_candidate, duplicate_candidate, candidate_features,
    candidates_for, version_label,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, normalize_receiving_layout, append_receiving_set,
    resize_receiving_bays,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def test_global_candidates_are_separate_by_role_and_not_bound_to_bays():
    lib = normalize_candidates()
    assert not candidates_for(lib, "head")
    assert not candidates_for(lib, "tail")
    lib, h1 = create_candidate(lib, "head", [{"x": 4}])
    lib, h2 = create_candidate(lib, "head", [{"x": 6}])
    lib, t1 = duplicate_candidate(lib, "head", h2, "tail")
    assert (h1, h2, t1) == ("head-v1", "head-v2", "tail-v1")
    assert [version_label(x) for x in (h1, h2, t1)] == [
        "版本一", "版本二", "版本一"
    ]
    other = update_candidate(lib, "head", h2, [{"x": 12}])
    assert candidate_features(other, "head", h2) == [{"x": 12}]
    assert candidate_features(other, "tail", t1) == [{"x": 6}]
    assert candidate_features(lib, "head", h2) == [{"x": 6}]
    deleted = delete_candidate(other, "head", h1)
    deleted, h3 = create_candidate(deleted, "head", [])
    assert h3 == "head-v3"  # deleted sequence numbers are never reused
    assert candidate_features(deleted, "head", h3) == []
    assert candidate_features(deleted, "tail", t1) == [{"x": 6}]


def test_candidate_copy_and_snapshot_boundaries():
    lib, head = create_candidate(None, "head", [{"dimension": [1, 2]}])
    value = candidate_features(lib, "head", head)
    value[0]["dimension"].append(99)
    assert candidate_features(lib, "head", head) == [{"dimension": [1, 2]}]
    copied, tail = duplicate_candidate(lib, "head", head, "tail")
    copied = update_candidate(copied, "tail", tail, [])
    assert candidate_features(copied, "head", head) == [{"dimension": [1, 2]}]
    assert candidate_features(copied, "tail", tail) == []
    assert candidate_features(lib, "head", head) == [{"dimension": [1, 2]}]


def test_candidate_library_survives_receiving_layout_normalize_set_resize():
    layout = new_receiving_layout(width=800, height=1100, depth=400)
    adapter = ReceivingSetBayAdapter(layout)
    assert "hole_candidates" not in adapter.layout
    lib, head = create_candidate(adapter.hole_candidates(), "head", [{"tag": "H"}])
    lib, tail = create_candidate(lib, "tail", [{"tag": "T"}])
    adapter.set_hole_candidates(lib)
    adapter.set_bay_count(3)
    adapter.set_set_count(2)
    saved = normalize_receiving_layout(adapter.layout)
    assert saved["hole_candidates"] == lib
    assert len(saved["sets"]) == 2
    assert len(saved["sets"][0]["bays"]) == 3
    restored = ReceivingSetBayAdapter(saved)
    assert candidate_features(restored.hole_candidates(), "head", head) == [{"tag": "H"}]
    assert candidate_features(restored.hole_candidates(), "tail", tail) == [{"tag": "T"}]
    assert "hole_candidates" not in normalize_receiving_layout(layout)


def test_candidate_validation_fails_closed():
    lib, head = create_candidate(None, "head", [])
    with pytest.raises(ValueError):
        create_candidate(lib, "door", [])
    with pytest.raises(ValueError):
        candidate_features(lib, "tail", head)
    with pytest.raises(ValueError):
        update_candidate(lib, "head", "head-v100", [])
    with pytest.raises(ValueError):
        duplicate_candidate(lib, "head", "head-v100", "tail")
    with pytest.raises(ValueError):
        delete_candidate(lib, "head", "head-v100")
    bad = deepcopy(lib)
    bad["head"]["next_number"] = 1
    with pytest.raises(ValueError):
        normalize_candidates(bad)
    bad = deepcopy(lib)
    bad["head"]["versions"].append(deepcopy(bad["head"]["versions"][0]))
    with pytest.raises(ValueError):
        normalize_candidates(bad)
    bad = deepcopy(lib)
    bad["tail"]["versions"] = [bad["head"]["versions"][0]]
    with pytest.raises(ValueError):
        normalize_candidates(bad)


def test_hole_editor_confirm_only_callback_never_runs_on_cancel():
    from gui_modules.editors.hole_editor import _HoleEditorModalLifecycle

    class Session:
        def __init__(self):
            self.commits = []
        def finish(self, commit):
            self.commits.append(commit)

    class Editor:
        def __init__(self):
            self.destroyed = False
        def destroy(self):
            self.destroyed = True

    def make():
        session, editor, events = Session(), Editor(), []
        modal = _HoleEditorModalLifecycle(
            hole_session=session,
            has_selected_feature=lambda: False,
            position_authority=[""],
            commit_active_edit=lambda **_kwargs: None,
            sync_all=lambda: events.append("sync"),
            validate_current_indicator_fit=lambda **_kwargs: True,
            door_indicator_state=None,
            collect_indicator_state=lambda: None,
            door_indicator_commit=None,
            editor_closed=[False], editor=editor,
            on_close=lambda: events.append("close"),
            on_confirm=lambda: events.append("persist"),
            insert_mode=[False], set_insert_mode=lambda _: None,
            cancel_active_edit=lambda: None,
        )
        return modal, session, events

    modal, session, events = make()
    modal.cancel_all()
    assert session.commits == [False]
    assert events == ["sync", "close"]
    modal, session, events = make()
    modal.confirm_all()
    assert session.commits == [True]
    assert events == ["sync", "persist", "close"]
