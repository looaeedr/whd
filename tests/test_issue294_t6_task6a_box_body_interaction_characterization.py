from __future__ import annotations

from types import SimpleNamespace

import gui


class Var:
    def __init__(self, value=None):
        self.value = value
        self.set_calls = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.set_calls.append(value)


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def itemconfigure(self, tag, **kwargs):
        self.calls.append((tag, kwargs))


def test_task6a_box_body_face_hit_test_and_selection_are_stable():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.box_body_face_bounds = {
        "left": (0.0, 0.0, 100.0, 100.0),
        "back": (110.0, 0.0, 210.0, 100.0),
        "right": (220.0, 0.0, 320.0, 100.0),
    }
    host.box_body_face_selected_var = Var()
    host.canvas_z = FakeCanvas()
    host.COLOR_ACCENT = "#0af"

    assert host._box_body_face_at_canvas_point(25.0, 25.0) == "left"
    assert host._box_body_face_at_canvas_point(150.0, 50.0) == "back"
    assert host._box_body_face_at_canvas_point(999.0, 999.0) is None

    host.select_box_body_face("back")
    assert host.box_body_face_selected_var.value == "back"
    assert host.canvas_z.calls == [
        ("box_body_face_left", {"outline": "#30d158", "width": 2}),
        ("box_body_face_back", {"outline": "#0af", "width": 3}),
        ("box_body_face_right", {"outline": "#30d158", "width": 2}),
    ]

    host.select_box_body_face("bogus")
    assert host.box_body_face_selected_var.value == "back"
    assert len(host.canvas_z.calls) == 3


def test_task6a_box_body_press_prefers_selected_physical_piece_face():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.box_body_piece_2d_selected_var = Var("box_body:left")
    host.box_body_face_selected_var = Var()
    host._box_body_piece_face_key = lambda key: "left" if key == "box_body:left" else None
    host._box_body_face_last_click = None
    host._box_body_face_at_canvas_point = lambda *_args: (_ for _ in ()).throw(
        AssertionError("physical piece route must bypass face hit-test")
    )

    assert host.on_box_body_canvas_press(
        SimpleNamespace(x=500.0, y=500.0, time=1000)
    ) == "break"
    assert host.box_body_face_selected_var.value == "left"


def test_task6a_box_body_press_selects_then_manual_double_click_opens_editor():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.box_body_piece_2d_selected_var = Var("")
    host.box_body_face_selected_var = Var()
    host._box_body_piece_face_key = lambda _key: None
    host.box_body_face_bounds = {"right": (10.0, 20.0, 110.0, 120.0)}
    host._box_body_face_last_click = None
    events = []
    host.select_box_body_face = lambda face: events.append(("select", face))
    host.open_box_body_face_editor = lambda face: events.append(("open", face))

    first = SimpleNamespace(x=50.0, y=60.0, time=1000)
    second = SimpleNamespace(x=50.0, y=60.0, time=1500)

    assert host.on_box_body_canvas_press(first) == "break"
    assert events == [("select", "right")]
    assert host._box_body_face_last_click == ("right", 1000)

    assert host.on_box_body_canvas_press(second) == "break"
    assert events == [("select", "right"), ("open", "right")]
    assert host._box_body_face_last_click is None


def test_task6a_box_body_press_miss_clears_pending_click():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.box_body_piece_2d_selected_var = Var("")
    host.box_body_face_selected_var = Var()
    host._box_body_piece_face_key = lambda _key: None
    host.box_body_face_bounds = {"left": (0.0, 0.0, 10.0, 10.0)}
    host._box_body_face_last_click = ("left", 100)
    host.select_box_body_face = lambda *_args: (_ for _ in ()).throw(
        AssertionError("miss must not select")
    )
    host.open_box_body_face_editor = lambda *_args: (_ for _ in ()).throw(
        AssertionError("miss must not open")
    )

    assert host.on_box_body_canvas_press(
        SimpleNamespace(x=50.0, y=50.0, time=500)
    ) == "break"
    assert host._box_body_face_last_click is None


def test_primary_box_body_hole_editor_cancel_refreshes_phase6_view_without_canvas_z():
    from gui_modules.editors.hole_editor import HoleEditorModalLifecycle

    app = gui.Phase6PrimaryApplication.__new__(gui.Phase6PrimaryApplication)
    app._phase6_primary_workspace = True
    app.box_body_face_selected_var = Var()
    app.box_body_face_features = {"left": []}
    app.baseline_var = Var("受電箱")
    app.get_float_values = lambda: {
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
    }
    app._box_body_corner_policies = lambda _fw: (None, None)
    app._box_body_face_baseline_scene = lambda _face_key, _val: None

    captured = {}
    app._open_unified_hole_editor = (
        lambda *args, **kwargs: captured.update(kwargs) or "EDITOR"
    )
    preview_calls = []
    app.draw_preview = lambda: preview_calls.append("preview")
    app.draw_box_body = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("primary lifecycle must not call legacy canvas_z refresh")
    )

    assert not hasattr(app, "canvas_z")
    assert app.open_box_body_face_editor("left") == "EDITOR"
    assert callable(captured["on_close"])

    session_finish = []
    editor_destroy = []
    lifecycle = HoleEditorModalLifecycle(
        hole_session=SimpleNamespace(
            finish=lambda *, commit: session_finish.append(commit),
            has_active_edit=False,
        ),
        has_selected_feature=lambda: False,
        position_authority=["direct"],
        commit_active_edit=lambda **_kwargs: None,
        sync_all=lambda: None,
        validate_current_indicator_fit=lambda **_kwargs: True,
        door_indicator_state=None,
        collect_indicator_state=lambda: None,
        door_indicator_commit=None,
        editor_closed=[False],
        editor=SimpleNamespace(destroy=lambda: editor_destroy.append(True)),
        on_close=captured["on_close"],
        insert_mode=[False],
        set_insert_mode=lambda _enabled: None,
        cancel_active_edit=lambda: None,
    )

    lifecycle.cancel_all()

    assert session_finish == [False]
    assert editor_destroy == [True]
    assert preview_calls == ["preview"]

