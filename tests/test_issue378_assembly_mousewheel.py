from __future__ import annotations

from types import SimpleNamespace

import fold_designer_bridge as bridge


class _FakeCanvas:
    def __init__(self):
        self.calls = []

    def yview_scroll(self, steps, unit):
        self.calls.append((steps, unit))


def _run(delta=0, num=0):
    app = SimpleNamespace(assembly_parts_canvas=_FakeCanvas())
    result = bridge._phase6_scroll_assembly_parts(
        app,
        SimpleNamespace(delta=delta, num=num),
    )
    return result, app.assembly_parts_canvas.calls


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
