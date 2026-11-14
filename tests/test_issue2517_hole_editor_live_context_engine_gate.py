"""#2517: Hole Editor physical face context must be validated by public Engine."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.editors.hole_editor import (
    HoleEditorContextSwitcher,
    HoleEditorLiveContext,
)


def _context(*, width=120.25, height=180.5, part_key="door"):
    return {
        "feature_list": [],
        "surface": object(),
        "width": width,
        "height": height,
        "reference_guide": object(),
        "baseline_scene": object(),
        "part_key": part_key,
        "baseline_status_text": "",
    }


def _live(**changes):
    context = _context(**changes)
    return HoleEditorLiveContext(**{
        key: context[key] for key in (
            "feature_list", "surface", "width", "height",
            "reference_guide", "baseline_scene", "part_key",
        )
    })


@pytest.mark.parametrize("axis,bad", [
    ("width", True),
    ("height", False),
    ("width", float("nan")),
    ("height", float("inf")),
    ("width", 0),
    ("height", "-1"),
    ("width", None),
    ("height", "not-a-dimension"),
])
def test_constructor_rejects_untrusted_physical_face_before_editor_starts(axis, bad):
    with pytest.raises(ValueError):
        _live(**{axis: bad})


def test_valid_context_matches_public_engine_and_preserves_fractional_reload():
    live = _live(width="120.25", height="180.5")
    assert live.width == manufacturing_api.normalize_operator_source_dimension(
        "120.25", field="w",
    )
    assert live.height == manufacturing_api.normalize_operator_source_dimension(
        "180.5", field="h",
    )
    incoming = _context(
        width="99.875", height="133.125", part_key="indicator_box",
    )
    live.apply(incoming)
    assert (live.width, live.height, live.part_key) == (
        99.875, 133.125, "indicator_box",
    )
    assert live.surface is incoming["surface"]


@pytest.mark.parametrize("axis,bad", [
    ("width", True),
    ("height", float("nan")),
    ("height", None),
    ("width", -2),
])
def test_apply_rejects_raw_invalid_face_without_partial_context_mutation(axis, bad):
    live = _live()
    previous = live.as_dict()
    incoming = _context(width="95.5", height="112.75", part_key="indicator_door")
    incoming[axis] = bad
    with pytest.raises(ValueError):
        live.apply(incoming)
    assert live.as_dict() == previous
    assert live.surface is previous["surface"]
    assert live.feature_list is previous["feature_list"]


def _switcher(target):
    events = []
    live = _live()
    session = SimpleNamespace(
        has_active_edit=True,
        active_features=live.feature_list,
        activate_context=lambda *_args: events.append("activate"),
    )
    insert_mode = [True]
    active_part = ["door"]
    position = ["existing-reference"]
    button = SimpleNamespace(configure=lambda **_kwargs: events.append("button"))
    status = SimpleNamespace(set=lambda _value: events.append("status"))
    switcher = HoleEditorContextSwitcher(
        live_context=live,
        hole_session=session,
        door_context=_context(),
        indicator_contexts={"indicator_box": target},
        cancel_active_edit=lambda: events.append("cancel"),
        insert_mode=insert_mode,
        insert_button=button,
        active_part_key=active_part,
        position_authority=position,
        baseline_status_var=status,
        baseline_status_label=None,
        baseline_status_color=lambda *_args: "grey",
        refresh_created=lambda: events.append("refresh"),
        refresh_reference_fields=lambda: events.append("references"),
        redraw=lambda: events.append("redraw"),
    )
    return switcher, live, events, insert_mode, active_part, position


def test_invalid_switch_keeps_hole_edit_selection_session_and_render_untouched():
    target = _context(width=True, height="75.5", part_key="indicator_box")
    switcher, live, events, insert_mode, active_part, position = _switcher(target)
    before = live.as_dict()
    with pytest.raises(ValueError):
        switcher.switch("indicator_box")
    assert events == []
    assert insert_mode == [True]
    assert active_part == ["door"]
    assert position == ["existing-reference"]
    assert live.as_dict() == before


def test_unknown_switch_target_does_not_cancel_active_edit():
    switcher, live, events, insert_mode, active_part, _ = _switcher(_context())
    before = live.as_dict()
    assert switcher.switch("missing-part") is False
    assert events == []
    assert insert_mode == [True]
    assert active_part == ["door"]
    assert live.as_dict() == before


def test_valid_switch_uses_same_engine_qualified_face_dimensions():
    target = _context(
        width="75.125", height="155.75", part_key="indicator_box",
    )
    switcher, live, events, insert_mode, active_part, position = _switcher(target)
    assert switcher.switch("indicator_box") is True
    assert (live.width, live.height) == (75.125, 155.75)
    assert active_part == ["indicator_box"]
    assert insert_mode == [False]
    assert position == [None]
    assert events == [
        "cancel", "button", "activate", "status", "refresh",
        "references", "redraw",
    ]
