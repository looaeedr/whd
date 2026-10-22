# -*- coding: utf-8 -*-
"""#1504: invalid Receiving NFB/ordinary HoleEditor full-preview is atomic.

These tests exercise the actual native shared HoleEditor session, not a
second NFB transaction implementation. No manufacturing/X authority granted.
"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession


@dataclass(frozen=True)
class Hole:
    name: str
    source_type: str = "NFB_CSV_SOURCE"


def test_bad_full_preview_selection_does_not_overwrite_original_live_nfb_holes():
    existing = [Hole("kept"), Hole("manual", "OPERATOR_HOLE")]
    identity = id(existing)
    session = Phase6HoleEditorSession("inner_door:0:panel", existing)
    before = session.snapshot()
    for invalid in (-2, 2, 99):
        with pytest.raises(IndexError):
            session.execute(HoleEditorAction.preview_all(
                [Hole("new-one"), Hole("new-two")], selected_index=invalid
            ))
        assert id(existing) == identity
        assert existing == [Hole("kept"), Hole("manual", "OPERATOR_HOLE")]
        assert session.snapshot() == before
        assert session.has_active_edit is False
    assert session.snapshot().undo_depth == 0


def test_rejected_nfb_full_preview_preserves_existing_active_edit_and_cancel():
    existing = [Hole("baseline")]
    session = Phase6HoleEditorSession("inner_door:0:panel", existing)
    session.execute(HoleEditorAction.preview_all([Hole("pending")]))
    before = session.snapshot()
    assert before.active_edit and existing == [Hole("pending")]
    with pytest.raises(IndexError):
        session.execute(HoleEditorAction.preview_all(
            [Hole("invalid")], selected_index=3
        ))
    assert session.snapshot() == before
    assert existing == [Hole("pending")]
    # Cancel All/Cancel Active must still revert to the true prior contents.
    session.execute(HoleEditorAction.cancel_active())
    assert existing == [Hole("baseline")]
    assert not session.has_active_edit


def test_valid_nfb_full_preview_can_undo_and_cancel_without_touching_other_holes():
    original = [Hole("operator-cutting", "OPERATOR_HOLE"), Hole("old-csv")]
    existing = list(original)
    session = Phase6HoleEditorSession("inner_door:0:panel", existing)
    staged = [original[0], Hole("new-csv")]
    accepted = session.execute(HoleEditorAction.preview_all(staged, selected_index=1))
    assert accepted.selected_index == 1
    assert existing == staged
    session.execute(HoleEditorAction.commit_active())
    assert session.snapshot().undo_depth == 1
    session.execute(HoleEditorAction.undo())
    assert existing == original
    session.execute(HoleEditorAction.preview_all(staged, selected_index=-1))
    assert existing == staged
    session.finish(commit=False)
    assert existing == original


def test_receiving_nfb_tab_reuses_native_preview_all_instead_of_bypassing_session():
    src = (Path(__file__).resolve().parents[1]
           / "gui_modules" / "editors" / "hole_editor_composition.py"
           ).read_text(encoding="utf-8")
    start = src.index("def stage_selected_nfb_openings(openings):")
    end = src.index("s.editor._receiving_stage_selected_nfb_openings =", start)
    body = src[start:end]
    assert "HoleEditorAction.preview_all(" in body
    assert "s.hole_session.execute(" in body
    assert "if feature_is_strictly_within_surface" not in body
    assert 'source_type != "NFB_CSV_SOURCE"' in body
