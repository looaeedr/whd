"""R5 #93: the *existing* Hole Editor controls reject NaN/Inf text.

Exercise the actual view-controller methods without creating or mocking a
manufacturing scene. No fake physical/DXF pass is inferred from these tests.
"""
from types import SimpleNamespace

import pytest

from gui_modules.editors.hole_editor import HoleEditorReferenceActions
from gui_modules.editors.hole_editor_round_settings import _RoundHoleSettingsDialog


class _Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _reference_actions(raw):
    """Create real controller without a Tk window or a live file."""
    calls = []
    old = object()
    control = object.__new__(HoleEditorReferenceActions)
    control.suppress_entry_events = [False]
    control.context_provider = lambda: {
        "feature_list": [old], "surface": "test",
        "width": 800., "height": 1100.,
    }
    control.hole_session = SimpleNamespace(selected_index=0)
    control.reference_variables = {("x", "edge"): _Variable(raw)}
    control.show_format_error = lambda: calls.append("error")
    control.refresh_reference_fields = lambda: calls.append("refresh")
    control.feature_reference_anchor = lambda _feature: "center"
    control.active_reference_guide = lambda: None

    def unchanged_move(*args, **kwargs):
        calls.append(("move", kwargs["value"]))
        return old

    control.move_feature_by_reference_distance = unchanged_move
    return control, calls


@pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "-inf", "Infinity", "1e999"])
@pytest.mark.parametrize("show_errors", [False, True])
def test_r5_93_reference_edit_rejects_nonfinite_before_geometry_mutation(raw, show_errors):
    actions, calls = _reference_actions(raw)
    actions.apply_reference_value("x", "edge", show_errors=show_errors)
    assert calls == (["error", "refresh"] if show_errors else [])


def test_r5_93_reference_finite_distance_keeps_existing_movement_path():
    actions, calls = _reference_actions("12.5")
    actions.apply_reference_value("x", "edge", show_errors=True)
    assert calls == [("move", 12.5), "refresh"]


def _round_dialog(*, center="25", gap="15", driver="center"):
    dialog = object.__new__(_RoundHoleSettingsDialog)
    dialog.sync_guard = False
    dialog.round_center = _Variable(center)
    dialog.round_gap = _Variable(gap)
    dialog.round_driver = _Variable(driver)
    dialog.selected_feature = SimpleNamespace(diameter=10.)
    return dialog


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "1e999"])
def test_r5_93_center_sync_keeps_previous_gap_on_nonfinite_input(raw):
    dialog = _round_dialog(center=raw, gap="unchanged", driver="gap")
    dialog._sync_from_center()
    assert dialog.round_gap.get() == "unchanged"
    assert dialog.round_driver.get() == "gap"
    assert dialog.sync_guard is False


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "1e999"])
def test_r5_93_gap_sync_keeps_previous_center_on_nonfinite_input(raw):
    dialog = _round_dialog(center="unchanged", gap=raw, driver="center")
    dialog._sync_from_gap()
    assert dialog.round_center.get() == "unchanged"
    assert dialog.round_driver.get() == "center"
    assert dialog.sync_guard is False


@pytest.mark.parametrize("driver", ["center", "gap"])
@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "1e999"])
def test_r5_93_round_commit_rejects_nonfinite_without_preview(driver, raw):
    dialog = _round_dialog(center=raw if driver == "center" else "25",
                           gap=raw if driver == "gap" else "15",
                           driver=driver)
    with pytest.raises(ValueError, match="有限"):
        dialog._driver_value()


def test_r5_93_round_valid_center_and_zero_gap_remain_allowed():
    dialog = _round_dialog(center="25", gap="15", driver="center")
    assert dialog._driver_value() == 25.
    dialog._sync_from_center()
    assert float(dialog.round_gap.get()) == pytest.approx(15.)
    dialog.round_gap.set("0")
    dialog._sync_from_gap()
    assert dialog.round_driver.get() == "gap"
    assert float(dialog.round_center.get()) == pytest.approx(10.)
    assert dialog._driver_value() == 0.
