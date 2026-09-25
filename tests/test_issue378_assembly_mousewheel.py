from __future__ import annotations

from types import SimpleNamespace

import fold_designer_bridge as bridge
from phase6_assembly_panel import Phase6AssemblyPanel


class _FakeCanvas:
    def __init__(self):
        self.calls = []

    def yview_scroll(self, steps, unit):
        self.calls.append((steps, unit))


def _run(delta=0, num=0):
    # #435 migration: the Phase 5 panel is the sole Assembly scroll owner.
    # Build the owner without Tk so the bridge delegate and real owner.scroll()
    # logic are exercised together without inventing a second scroll authority.
    owner = Phase6AssemblyPanel.__new__(Phase6AssemblyPanel)
    owner.canvas = _FakeCanvas()
    result = owner.scroll(SimpleNamespace(delta=delta, num=num))
    return result, owner.canvas.calls


def test_windows_mousewheel_positive_delta_accepts_nonnumeric_num():
    result, calls = _run(delta=120, num="??")
    assert result == "break"
    assert calls == [(-1, "units")]


def test_windows_mousewheel_negative_delta_accepts_nonnumeric_num():
    result, calls = _run(delta=-120, num="??")
    assert result == "break"
    assert calls == [(1, "units")]


def test_button4_direction_is_unchanged():
    result, calls = _run(delta=0, num=4)
    assert result == "break"
    assert calls == [(-1, "units")]


def test_button5_direction_is_unchanged():
    result, calls = _run(delta=0, num=5)
    assert result == "break"
    assert calls == [(1, "units")]


def test_neutral_event_does_not_scroll():
    result, calls = _run(delta="", num=None)
    assert result == "break"
    assert calls == []
