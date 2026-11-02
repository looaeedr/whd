"""#2517: Receiving inner-door Hole Editor consumes Engine physical identity."""

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import receiving_inner_door_hole_editor as editor


@pytest.mark.parametrize(
    ("part_key", "role"),
    (
        ("inner_door:upper:panel", "inner"),
        ("inner_door:lower:panel", "inner"),
        ("inner_door:upper:left_frame", "other"),
        ("inner_door:upper:panel:preview", "other"),
        ("door", "outer"),
        ("door_c1_r1", "outer"),
        ("box_body:left", "other"),
        (None, "other"),
    ),
)
def test_inner_door_hole_editor_uses_canonical_engine_physical_role(part_key, role):
    assert manufacturing_api.door_display_part_role(part_key) == role
    assert editor.is_inner_door_sheet(part_key) is (role == "inner")


def test_inner_door_hole_editor_fail_closed_before_accessing_gui_for_other_parts():
    # The entry point must reject non-panel physical parts before opening a
    # window or writing staged NFB/feature state.
    for part_key in ("door", "inner_door:upper:left_frame", "box_body:left"):
        with pytest.raises(ValueError, match="不是可開孔編輯的內門門板"):
            editor.open_inner_door_hole_editor(None, part_key)


def test_inner_door_hole_editor_does_not_reimplement_role_recognition(monkeypatch):
    observed = []

    def engine_role(value):
        observed.append(value)
        return "other"

    monkeypatch.setattr(manufacturing_api, "door_display_part_role", engine_role)
    assert editor.is_inner_door_sheet("inner_door:upper:panel") is False
    assert observed == ["inner_door:upper:panel"]
